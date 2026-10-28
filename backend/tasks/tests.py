"""tasks 的回归测试（#088 还债轮）。

为什么现在写：TaskDay 把"完成"从"一个全局布尔"改成"按天流水"之后，
每日重置、配额剩余、取消勾选、删步骤这四件事全挤在 `_apply_day` 一个函数里算。
这几处一旦回退（比如又去读 `step.is_done`），界面表现是"昨天的成绩冒充今天"，
而人肉点是看不出来的 —— 所以这里锁的是"行为",不是实现细节。

跑法：
    python manage.py test tasks -v 2
"""

import json
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings

from quick.models import QuickPattern, QuickStep
from tasks.models import TaskDay, UserTask, UserTaskStep, local_today
from users.models import User

TODAY = local_today()
WEEK_START = TODAY - timedelta(days=TODAY.weekday())   # 本周一


class TaskDayTestBase(TestCase):
    """建用户 + 造任务的小工具。所有接口都走 HTTP（带 Token），连路由和认证一起测。"""

    def setUp(self):
        self.user = User.objects.create(email='task-tester@example.com')
        self.user.set_password('pass-123456')
        self.user.save()                      # api_token 在 save() 里自动生成
        self.auth = {'HTTP_AUTHORIZATION': 'Token ' + self.user.api_token}

    def make_task(self, freq='once', steps=2, **extra):
        task = UserTask.objects.create(
            user=self.user, title='测试任务', frequency_type=freq, **extra
        )
        for i in range(steps):
            UserTaskStep.objects.create(task=task, order=i + 1, title='第 %d 步' % (i + 1))
        return task

    def make_day(self, task, on_date, done_ids, completed=True):
        return TaskDay.objects.create(
            user=self.user, task=task, date=on_date,
            done_step_ids=[int(i) for i in done_ids],
            done_count=len(done_ids), completed=completed,
        )

    def tick(self, task, step_id, value=True):
        return self.client.patch(
            '/api/v1/tasks/%d/steps/%d/' % (task.pk, step_id),
            data=json.dumps({'is_done': value}),
            content_type='application/json', **self.auth
        )

    def list_tasks(self, query='', **kwargs):
        return self.client.get('/api/v1/tasks/' + query, **dict(self.auth, **kwargs))

    def row(self, task_id, query=''):
        data = self.list_tasks(query).json()['data']
        for t in data['items']:
            if t['id'] == task_id:
                return t
        return None


class TodayResetTests(TaskDayTestBase):
    """① 昨天做完的，今天打开必须是 0（不串昨天的成绩）"""

    def test_yesterday_done_does_not_leak_into_today(self):
        task = self.make_task('habit', steps=2)
        ids = list(task.steps.values_list('id', flat=True))
        self.make_day(task, TODAY - timedelta(days=1), ids)      # 昨天全做完了
        # 老数据残留：is_done 还停在 True（#087 之前就是这样存的）
        UserTaskStep.objects.filter(task=task).update(is_done=True)

        row = self.row(task.pk)
        self.assertEqual(row['steps_done'], 0, '昨天的勾漏进今天了')
        self.assertFalse(row['done_today'])
        self.assertFalse(row['steps'][0]['is_done'] if row.get('steps') else False)

    def test_tick_all_steps_creates_completed_day(self):
        task = self.make_task('once', steps=2)
        ids = list(task.steps.order_by('order').values_list('id', flat=True))

        first = self.tick(task, ids[0]).json()['data']
        self.assertEqual(first['change'], '')            # 只勾了一步，不该有完成事件
        last = self.tick(task, ids[1]).json()['data']
        self.assertEqual(last['change'], 'completed')    # 勾完最后一步 → 今天这张做完了

        day = TaskDay.objects.get(task=task, date=TODAY)
        self.assertEqual(day.done_count, 2)
        self.assertTrue(day.completed)

    def test_uncheck_reuses_same_day_row(self):
        """取消勾选是【改】今天那条，不是再插一条 —— 否则一天会攒出好几行"""
        task = self.make_task('habit', steps=2)
        ids = list(task.steps.order_by('order').values_list('id', flat=True))
        self.tick(task, ids[0])
        self.tick(task, ids[1])
        self.assertEqual(TaskDay.objects.filter(task=task, date=TODAY).count(), 1)

        self.tick(task, ids[0], False)
        self.assertEqual(TaskDay.objects.filter(task=task, date=TODAY).count(), 1)
        day = TaskDay.objects.get(task=task, date=TODAY)
        self.assertEqual(day.done_step_ids, [ids[1]])
        self.assertFalse(day.completed)


class QuotaTests(TaskDayTestBase):
    """② 配额"还剩 N 次"按【本周期】算，不是拿历史累计的 done_count 减"""

    def _quota_task(self):
        # target_count 必须给：留空表示"不限次数"，remaining_count 会返回 None
        return self.make_task('quota', steps=1, quota_period='week',
                              quota_count=3, target_count=3)

    def test_remaining_counts_days_in_this_week(self):
        task = self._quota_task()
        sid = task.steps.first().pk
        done_dates = [WEEK_START]
        if WEEK_START != TODAY:
            done_dates.append(TODAY)
        for d in done_dates:
            self.make_day(task, d, [sid])

        self.assertEqual(task.remaining_count, 3 - len(done_dates))

    def test_remaining_resets_when_week_changes(self):
        """上周做的次数不该算进本周 —— 周一打开应该是满额"""
        task = self._quota_task()
        sid = task.steps.first().pk
        self.make_day(task, WEEK_START - timedelta(days=1), [sid])   # 上周日

        self.assertEqual(task.remaining_count, 3)

    def test_done_count_is_not_used_for_remaining(self):
        """done_count 是历史累计，用它算剩余就会越用越少（#087 的病根）"""
        task = self._quota_task()
        task.done_count = 99
        task.save(update_fields=['done_count'])

        self.assertEqual(task.remaining_count, 3)


class OnceTaskTests(TaskDayTestBase):
    """③ once 全勾 → 结单，不再出现在"进行中\""""

    def test_once_marks_done_and_leaves_active_list(self):
        task = self.make_task('once', steps=1)
        sid = task.steps.first().pk
        self.tick(task, sid)

        task.refresh_from_db()
        self.assertEqual(task.status, 'done')
        self.assertEqual(task.remaining_count, 0)

        active_ids = [t['id'] for t in self.list_tasks('?status=active').json()['data']['items']]
        self.assertNotIn(task.pk, active_ids)

    def test_habit_stays_active_after_finishing(self):
        """habit 今天做完仍然是 active：明天还要出现，从 0 重新开始"""
        task = self.make_task('habit', steps=1)
        self.tick(task, task.steps.first().pk)

        task.refresh_from_db()
        self.assertEqual(task.status, 'active')


class DeleteStepTests(TaskDayTestBase):
    """④ 删步骤：当天 TaskDay 要跟着摘掉那个 id，不能比实际步数还大"""

    def test_delete_step_cleans_today_day(self):
        task = self.make_task('habit', steps=2)
        ids = list(task.steps.order_by('order').values_list('id', flat=True))
        self.tick(task, ids[0])
        self.tick(task, ids[1])

        resp = self.client.delete(
            '/api/v1/tasks/%d/steps/%d/' % (task.pk, ids[0]), **self.auth
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['deleted_step'], ids[0])

        day = TaskDay.objects.get(task=task, date=TODAY)
        self.assertEqual(day.done_step_ids, [ids[1]])
        self.assertEqual(day.done_count, 1)
        # 删掉的是一步【已做】的，剩下的那步也做了 → 整张仍然算做完，别把已完成改回未完成
        self.assertTrue(day.completed)

    def test_delete_done_step_makes_task_unfinished(self):
        """只做了一步、然后把那一步删了 → 今天这件事又回到"没做完\""""
        task = self.make_task('habit', steps=2)
        ids = list(task.steps.order_by('order').values_list('id', flat=True))
        self.tick(task, ids[0])

        self.client.delete('/api/v1/tasks/%d/steps/%d/' % (task.pk, ids[0]), **self.auth)

        day = TaskDay.objects.get(task=task, date=TODAY)
        self.assertEqual(day.done_step_ids, [])
        self.assertEqual(day.done_count, 0)
        self.assertFalse(day.completed)


class TaskListPagingTests(TaskDayTestBase):
    """⑤ /tasks/ 分页：带 page 才分页，不带就保持老契约"""

    def setUp(self):
        super().setUp()
        for i in range(5):
            UserTask.objects.create(user=self.user, title='任务 %d' % i, frequency_type='once')

    def test_paged_response_shape(self):
        data = self.list_tasks('?page=1&page_size=2').json()['data']
        self.assertEqual(data['count'], 5)
        self.assertEqual(len(data['results']), 2)
        self.assertIsNotNone(data['next'])
        self.assertIsNone(data['previous'])
        self.assertIn('page=2', data['next'])

    def test_last_page_has_no_next(self):
        data = self.list_tasks('?page=3&page_size=2').json()['data']
        self.assertEqual(len(data['results']), 1)
        self.assertIsNone(data['next'])
        self.assertIsNotNone(data['previous'])

    def test_page_size_is_clamped(self):
        UserTask.objects.all().delete()
        UserTask.objects.bulk_create([
            UserTask(user=self.user, title='批量 %d' % i, frequency_type='once') for i in range(105)
        ])
        data = self.list_tasks('?page_size=999').json()['data']
        self.assertEqual(data['count'], 105)
        self.assertEqual(len(data['results']), 100)     # 被钳到上限 100

    def test_no_page_keeps_old_contract(self):
        """老客户端（H5 / 小程序）现在都不带 page：必须还是一次全量 + items"""
        data = self.list_tasks().json()['data']
        self.assertEqual(len(data['items']), 5)
        self.assertEqual(data['count'], 5)
        self.assertNotIn('results', data)


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
}})
class LoginLockTests(TestCase):
    """⑥ 登录限流：连错 5 次锁 10 分钟，锁定期即使密码对也不放行

    这里覆盖缓存后端：线上用 DatabaseCache（pattern_cache 表），测试库不会建那张表，
    不换成本地内存缓存的话，限流会因为"缓存读不到"而静默失效，测试假绿。
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create(email='lock-me@example.com')
        self.user.set_password('right-pass')
        self.user.save()

    def login(self, password, email='lock-me@example.com'):
        return self.client.post(
            '/api/v1/auth/login/',
            data=json.dumps({'email': email, 'password': password}),
            content_type='application/json',
        )

    def test_locks_after_five_failures(self):
        for i in range(5):
            self.assertEqual(self.login('wrong-%d' % i).status_code, 400, '第 %d 次不该锁' % (i + 1))

        resp = self.login('wrong-again')
        self.assertEqual(resp.status_code, 429)
        self.assertIn('歇', resp.json()['data']['error'])     # 文案有温度，不是"操作过于频繁"

    def test_locked_even_with_correct_password(self):
        for i in range(5):
            self.login('wrong-%d' % i)
        self.assertEqual(self.login('right-pass').status_code, 429)

    def test_another_email_is_not_locked(self):
        for i in range(5):
            self.login('wrong-%d' % i)
        other = User.objects.create(email='other@example.com')
        other.set_password('right-pass')
        other.save()
        self.assertEqual(self.login('right-pass', email='other@example.com').status_code, 200)

    def test_success_clears_counter(self):
        for i in range(4):
            self.login('wrong-%d' % i)
        self.assertEqual(self.login('right-pass').status_code, 200)   # 成功一次 → 计数清零
        # 清零后再错 4 次也不该锁（如果没清零，第 5 次就锁了）
        for i in range(4):
            self.assertEqual(self.login('wrong-x-%d' % i).status_code, 400)

class TodayDefinitionTests(TaskDayTestBase):
    """#089 ①：「今天的任务」= active 且 plan_date=今天，三处同一个口径

    以前任务页拿的是"全部 active"，排到明年的事也算今天 →
    顶部永远挂着"还有 N 项"，allDone 永远不成立；而日程页说今天没事。
    """

    def test_today_query_excludes_future_and_unscheduled(self):
        today_task = self.make_task('once', plan_date=TODAY)
        self.make_task('once', plan_date=TODAY + timedelta(days=3))      # 排到三天后
        self.make_task('once')                                          # 没排日子
        archived = self.make_task('once', plan_date=TODAY)
        UserTask.objects.filter(pk=archived.pk).update(status='archived')

        data = self.list_tasks('?today=1').json()['data']
        ids = [t['id'] for t in data['items']]
        self.assertEqual(ids, [today_task.pk], '今天只该有排到今天、且还在进行中的那一条')
        self.assertEqual(data['unscheduled'], 1, '没排日子的单独报个数，前端才知道去哪儿找')

    def test_today_query_without_page_keeps_items_shape(self):
        # #088 的分页是 opt-in：不带 page 时 items 必须还在（老页面不该突然变空）
        self.make_task('once', plan_date=TODAY)
        data = self.list_tasks('?today=1').json()['data']
        self.assertIn('items', data)
        self.assertNotIn('results', data)

    def test_create_defaults_plan_date_to_today(self):
        resp = self.client.post(
            '/api/v1/tasks/',
            data=json.dumps({'title': '加入默认排今天'}),
            content_type='application/json', **self.auth
        )
        self.assertEqual(resp.status_code, 201)
        task = UserTask.objects.get(pk=resp.json()['data']['id'])
        self.assertEqual(task.plan_date, TODAY, '加入任务必须落在今天，否则用户加完看不见')

    def test_create_keeps_explicit_date_and_allows_clearing(self):
        future = TODAY + timedelta(days=5)
        resp = self.client.post(
            '/api/v1/tasks/',
            data=json.dumps({'title': '排到以后', 'plan_date': future.isoformat()}),
            content_type='application/json', **self.auth
        )
        self.assertEqual(UserTask.objects.get(pk=resp.json()['data']['id']).plan_date, future)
        # 显式传空 = 先不排期（从时间轴上撤下来），这是保留空值的唯一方式
        resp = self.client.post(
            '/api/v1/tasks/',
            data=json.dumps({'title': '先不定日子', 'plan_date': ''}),
            content_type='application/json', **self.auth
        )
        self.assertIsNone(UserTask.objects.get(pk=resp.json()['data']['id']).plan_date)


class CalendarPerDayTests(TaskDayTestBase):
    """#089 ③：日历的 tasks_completed 只算【当天】做完了的

    以前用一个全局 completed_ids 集合，昨天做完、今天只勾一半的任务
    会把昨天的完成算到今天（今天 0 件做完却报 1 件、rate 0.5）。
    """

    def test_completed_counts_only_its_own_day(self):
        task = self.make_task('habit', steps=2)
        ids = list(task.steps.values_list('id', flat=True))
        yesterday = TODAY - timedelta(days=1)
        self.make_day(task, yesterday, ids)                  # 昨天全做完
        self.make_day(task, TODAY, ids[:1], completed=False)  # 今天只勾一步

        data = self.client.get(
            '/api/v1/tasks/calendar/?month=%s' % TODAY.strftime('%Y-%m'), **self.auth
        ).json()['data']
        days = {d['date']: d for d in data['days']}
        y = days[yesterday.isoformat()]
        t = days[TODAY.isoformat()]
        self.assertEqual(y['tasks_completed'], 1, '昨天确实做完了')
        self.assertEqual(t['tasks_completed'], 0, '今天没做完，不能借用昨天的成绩')
        self.assertEqual(t['task_count'], 1)
        self.assertEqual(t['rate'], 0)


class ArchivedReadOnlyTests(TaskDayTestBase):
    """#089 ④：归档 = 收起来了，只读（以前归档任务还能勾，还会写今天那条流水）"""

    def test_archived_step_patch_is_403(self):
        task = self.make_task('habit', steps=2)
        step = task.steps.first()
        UserTask.objects.filter(pk=task.pk).update(status='archived')
        resp = self.tick(task, step.pk, True)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('收起来', resp.json()['data']['error'])
        self.assertFalse(TaskDay.objects.filter(task=task).exists(), '被拒了就不许写流水')

    def test_archived_step_create_is_403(self):
        task = self.make_task('habit', steps=1)
        UserTask.objects.filter(pk=task.pk).update(status='archived')
        resp = self.client.post(
            '/api/v1/tasks/%d/steps/' % task.pk,
            data=json.dumps({'title': '还想加一步'}),
            content_type='application/json', **self.auth
        )
        self.assertEqual(resp.status_code, 403)


class ForkGateTests(TaskDayTestBase):
    """#089 ⑤：allow_fork=False 也要拦「拆出来做」（以前只拦整份 fork，正文照样被复制走）"""

    def setUp(self):
        super().setUp()
        self.author = User.objects.create(email='fork-author@example.com')
        self.author.set_password('pass-123456')
        self.author.save()
        self.pattern = QuickPattern.objects.create(
            title='不让改的做法', author=self.author, allow_fork=False, is_listed=True,
        )
        self.step = QuickStep.objects.create(
            pattern=self.pattern, order=1, title='第一步', instruction='把手抬起来',
        )

    def test_from_step_blocked_when_allow_fork_false(self):
        resp = self.client.post(
            '/api/v1/tasks/from-step/',
            data=json.dumps({'step_id': self.step.pk}),
            content_type='application/json', **self.auth
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(UserTask.objects.filter(user=self.user).exists(), '被拒就不该建出任务')

    def test_whole_pattern_join_blocked_too(self):
        resp = self.client.post(
            '/api/v1/tasks/',
            data=json.dumps({'pattern_id': self.pattern.pk}),
            content_type='application/json', **self.auth
        )
        self.assertEqual(resp.status_code, 403)

    def test_author_can_still_use_own_pattern(self):
        resp = self.client.post(
            '/api/v1/tasks/from-step/',
            data=json.dumps({'step_id': self.step.pk}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Token ' + self.author.api_token,
        )
        self.assertEqual(resp.status_code, 201, '作者本人不受 allow_fork 限制')
