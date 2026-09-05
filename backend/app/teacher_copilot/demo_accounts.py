"""服务端固定体验账号白名单；初始化脚本和静默登录共享，禁止前端指定账号。"""

# 这些是公开体验数据的专用账号，不得替换为真实用户或管理员账号。
ACCOUNTS = [
    ("teacher@demo.com", "teacher123456", "user", "teacher", "teacher_01", "教师:王老师(演示账号)"),
    ("student@demo.com", "student123456", "user", "student", "stu_003", "学生:张三(演示账号)"),
]
