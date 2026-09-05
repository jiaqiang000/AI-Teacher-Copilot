import { expect, test, type Page } from "@playwright/test";

async function mockTeacherApis(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        id: "e2e-teacher",
        email: "teacher@demo.com",
        system_role: "admin",
        needs_setup: false,
        oauth_provider: null,
      },
    }),
  );
  await page.route("**/api/teacher-copilot/account/role", (route) =>
    route.fulfill({ json: { success: true, data: { role: "teacher" } } }),
  );
  await page.route("**/api/teacher-copilot/classes", (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { class_id: "class_03", name: "八三班", student_count: 30 },
          { class_id: "class_04", name: "八四班", student_count: 32 },
          { class_id: "class_05", name: "八五班", student_count: 28 },
        ],
      },
    }),
  );

  await page.route("**/api/teacher-copilot/profile/class/*", (route) => {
    const url = new URL(route.request().url());
    const classId = url.pathname.split("/").pop();
    const profiles = {
      class_03: {
        class_id: "class_03",
        class_name: "八三班",
        student_count: 30,
        avg_score_rate: 0.86,
        trend: "stable",
        weak_point: "移项与符号",
        attention_student_id: "stu_003",
      },
      class_04: {
        class_id: "class_04",
        class_name: "八四班",
        student_count: 32,
        avg_score_rate: 0.68,
        trend: "improving",
        weak_point: "合并同类项",
        attention_student_id: "stu_101",
      },
      class_05: {
        class_id: "class_05",
        class_name: "八五班",
        student_count: 28,
        avg_score_rate: 0.48,
        trend: "declining",
        weak_point: "函数图像",
        attention_student_id: "stu_201",
      },
    } as const;
    const profile = profiles[classId as keyof typeof profiles];
    if (!profile) {
      return route.fulfill({
        status: 404,
        json: { detail: { message: "班级不存在" } },
      });
    }
    return route.fulfill({
      json: {
        success: true,
        data: {
          basic: {
            class_id: profile.class_id,
            class_name: profile.class_name,
            subject: "math",
            algorithm_version: "profile_v1",
          },
          overview: {
            student_count: profile.student_count,
            active_student_count: profile.student_count,
            avg_score_rate: profile.avg_score_rate,
            recent_score_rate: profile.avg_score_rate,
            trend: profile.trend,
          },
          weak_points: [
            {
              knowledge_point_key: "math.demo." + profile.weak_point,
              avg_mastery: profile.avg_score_rate,
              weak_student_count: 6,
              trend: profile.trend,
            },
          ],
          common_errors: [],
          attention_students: [
            {
              student_id: profile.attention_student_id,
              weak_point_count: 2,
              recent_score_rate: profile.avg_score_rate,
              trend: profile.trend,
              reason_codes: ["LOW_RECENT_SCORE"],
            },
          ],
        },
      },
    });
  });

  await page.route("**/api/teacher-copilot/homework**", (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          {
            homework_id: "hw_004",
            name: "八年级数学周末作业",
            class_id: "class_03",
            class_name: "八三班",
            subject: "math",
            status: "PUBLISHED",
            published_at: "2026-09-05T10:00:00",
            deadline: null,
          },
        ],
      },
    }),
  );
  await page.route("**/api/teacher-copilot/analysis/homework**", (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          homework_id: "hw_004",
          class_id: "class_03",
          completion: {
            assigned_student_count: 30,
            submitted_student_count: 28,
            completion_rate: 0.9333,
          },
          performance: {
            graded_student_count: 27,
            avg_score_rate: 0.82,
            score_distribution: null,
          },
          knowledge_points: [],
          questions: [],
          attention_students: [],
        },
      },
    }),
  );
}

test.describe("教师巡检缺口：对象与入口", () => {
  test.beforeEach(async ({ page }) => {
    await mockTeacherApis(page);
  });

  test("班级列表进入详情时保持班级对象一致", async ({ page }) => {
    await page.goto("/workspace/teacher-copilot/classes");
    await expect(page.getByRole("link", { name: "八四班" })).toHaveAttribute(
      "href",
      "/workspace/teacher-copilot/classes/class_04",
    );

    await page.getByRole("link", { name: "八四班" }).click();
    await expect(page).toHaveURL(/\/classes\/class_04$/);
    await expect(page.getByRole("heading", { name: /八四班/ })).toBeVisible();
    await expect(page.getByText("32 名学生")).toBeVisible();
    await expect(page.getByText("改善")).toBeVisible();
    await expect(page.getByText("合并同类项")).toBeVisible();
  });

  test("重点学生入口携带真实学生 ID", async ({ page }) => {
    await page.goto("/workspace/teacher-copilot/classes/class_04");
    await expect(page.getByRole("link", { name: /stu_101/ })).toHaveAttribute(
      "href",
      "/workspace/teacher-copilot/students/stu_101?class_id=class_04",
    );
  });

  test("作业入口进入管理页并提供创建入口", async ({ page }) => {
    await page.goto("/workspace/teacher-copilot/homeworks");
    await expect(page.getByRole("heading", { name: "作业管理" })).toBeVisible();
    await expect(page.getByText("八年级数学周末作业")).toBeVisible();
    await expect(page.getByRole("link", { name: /创建作业/ })).toHaveAttribute(
      "href",
      "/workspace/teacher-copilot/homeworks/new/authoring",
    );
  });

  test("不存在的班级不显示八三班数据", async ({ page }) => {
    await page.goto("/workspace/teacher-copilot/classes/not-found");
    await expect(page.getByText(/班级不存在|加载失败/)).toBeVisible();
    await expect(page.getByText("八三班 · 数学")).toHaveCount(0);
  });

  test("375×812 窄屏展开后可见四项教师导航且没有横向滚动", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/workspace/teacher-copilot/dashboard");
    await page.locator('[data-slot="sidebar-trigger"]').click();
    await expect(page.getByRole("link", { name: "教师工作台" })).toBeVisible();
    await expect(page.getByRole("link", { name: "班级" })).toBeVisible();
    await expect(page.getByRole("link", { name: "作业", exact: true })).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Copilot 对话" }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(375);
  });
});

test.describe("学生巡检缺口：题目对象一致性", () => {
  test("有效 q001 使用真实题干并保留作答入口", async ({ page }) => {
    await page.route(
      "**/api/teacher-copilot/homework/hw_004/for-student",
      (route) =>
        route.fulfill({
          json: {
            success: true,
            data: {
              homework: {
                homework_id: "hw_004",
                name: "八年级数学周末作业",
                subject: "math",
                status: "PUBLISHED",
                deadline: null,
                published_at: "2026-09-05T10:00:00",
              },
              questions: [
                {
                  question_id: "q001",
                  question_no: 1,
                  question_type: "calculation",
                  content: "解方程 2x + 4 = 8",
                  max_score: 10,
                  difficulty: "easy",
                  my_submission: null,
                },
              ],
            },
          },
        }),
    );

    await page.goto(
      "/workspace/teacher-copilot/student/grading?homework_id=hw_004&question_id=q001",
    );
    await expect(page.getByRole("heading", { name: "第 1 题" })).toBeVisible();
    await expect(page.getByText("解方程 2x + 4 = 8")).toBeVisible();
    await expect(page.locator('input[type="file"]')).toHaveCount(1);
  });

  test("无效 question_id 显示错误且不回退或提交", async ({ page }) => {
    let submissionRequests = 0;
    await page.route(
      "**/api/teacher-copilot/homework/hw_004/for-student",
      (route) =>
        route.fulfill({
          json: {
            success: true,
            data: {
              homework: {
                homework_id: "hw_004",
                name: "八年级数学周末作业",
                subject: "math",
                status: "PUBLISHED",
                deadline: null,
                published_at: "2026-09-05T10:00:00",
              },
              questions: [
                {
                  question_id: "q001",
                  question_no: 1,
                  question_type: "calculation",
                  content: "解方程 2x + 4 = 8",
                  max_score: 10,
                  difficulty: "easy",
                  my_submission: null,
                },
              ],
            },
          },
        }),
    );
    await page.route("**/api/teacher-copilot/submissions**", (route) => {
      if (route.request().method() === "POST") submissionRequests += 1;
      return route.continue();
    });

    await page.goto(
      "/workspace/teacher-copilot/student/grading?homework_id=hw_004&question_id=q999",
    );
    await expect(page.getByText(/题目不存在|题目与作业不匹配/)).toBeVisible();
    await expect(page.locator('input[type="file"]')).toHaveCount(0);
    expect(submissionRequests).toBe(0);
    await expect(page.getByText("解方程 2x + 4 = 8")).toHaveCount(0);
  });
});

test.describe("教师巡检缺口：作业题目下钻", () => {
  test.beforeEach(async ({ page }) => {
    await mockTeacherApis(page);
    await page.route("**/api/teacher-copilot/homework/hw_004", (route) =>
      route.fulfill({
        json: {
          success: true,
          data: {
            homework_id: "hw_004",
            name: "八年级数学周末作业",
            class_id: "class_03",
            subject: "math",
            status: "PUBLISHED",
            published_at: "2026-09-05T10:00:00",
            deadline: null,
            questions: [
              {
                question_id: "q001",
                question_no: 1,
                question_type: "calculation",
                difficulty: "easy",
                content: "解方程 2x + 4 = 8",
                max_score: 10,
              },
              {
                question_id: "q002",
                question_no: 2,
                question_type: "solution",
                difficulty: "medium",
                content: "解含括号的一元一次方程",
                max_score: 10,
              },
            ],
          },
        },
      }),
    );
    await page.route(
      "**/api/teacher-copilot/analysis/homework/hw_004**",
      (route) =>
        route.fulfill({
          json: {
            success: true,
            data: {
              homework_id: "hw_004",
              class_id: "class_03",
              completion: {
                assigned_student_count: 30,
                submitted_student_count: 28,
                completion_rate: 0.9333,
              },
              performance: {
                graded_student_count: 27,
                avg_score_rate: 0.82,
                score_distribution: {
                  below_60: 3,
                  from_60_to_79: 8,
                  from_80_to_89: 10,
                  from_90_to_100: 6,
                },
              },
              knowledge_points: [],
              questions: [
                {
                  question_id: "q001",
                  question_no: 1,
                  attempt_count: 28,
                  avg_score_rate: 0.72,
                  error_student_count: 8,
                  error_rate: 0.2857,
                  common_errors: [
                    {
                      error_code: "SIGN_ERROR",
                      knowledge_point_key: "math.linear_equation.transposition",
                      occurrence_count: 8,
                      affected_student_count: 8,
                    },
                  ],
                },
                {
                  question_id: "q002",
                  question_no: 2,
                  attempt_count: 28,
                  avg_score_rate: 0.88,
                  error_student_count: 4,
                  error_rate: 0.1429,
                  common_errors: [],
                },
              ],
              attention_students: [],
            },
          },
        }),
    );
    await page.route(
      "**/api/teacher-copilot/analysis/question/q001**",
      (route) =>
        route.fulfill({
          json: {
            success: true,
            data: {
              question_id: "q001",
              question_no: 1,
              attempt_count: 28,
              avg_score_rate: 0.72,
              error_student_count: 8,
              error_rate: 0.2857,
              common_errors: [
                {
                  error_code: "SIGN_ERROR",
                  knowledge_point_key: "math.linear_equation.transposition",
                  occurrence_count: 8,
                  affected_student_count: 8,
                },
              ],
              content: "解方程 2x + 4 = 8",
              question_type: "calculation",
              difficulty: "easy",
              max_score: 10,
            },
          },
        }),
    );
  });

  test("题目表现行可点击并返回同一份作业分析", async ({ page }) => {
    await page.goto(
      "/workspace/teacher-copilot/homeworks/hw_004/analysis?class_id=class_03",
    );
    await expect(page.getByRole("link", { name: /第 1 题/ })).toHaveAttribute(
      "href",
      "/workspace/teacher-copilot/homeworks/hw_004/analysis?class_id=class_03&question_id=q001",
    );
    await page.getByRole("link", { name: /第 1 题/ }).click();
    await expect(page.getByRole("heading", { name: /第 1 题/ })).toBeVisible();
    await expect(page.getByText("解方程 2x + 4 = 8")).toBeVisible();
    await expect(page.locator("body")).toContainText("错误率29%");
    await page.getByRole("link", { name: /返回作业分析/ }).click();
    await expect(page).not.toHaveURL(/question_id/);
  });

  test("题目无有效数据时显示明确空状态和返回路径", async ({ page }) => {
    await page.route(
      "**/api/teacher-copilot/analysis/question/q002**",
      (route) =>
        route.fulfill({
          status: 404,
          json: { detail: { message: "题目无有效作答数据" } },
        }),
    );
    await page.goto(
      "/workspace/teacher-copilot/homeworks/hw_004/analysis?class_id=class_03&question_id=q002",
    );
    await expect(page.getByText("题目无有效作答数据")).toBeVisible();
    await expect(
      page.getByRole("link", { name: /返回作业分析/ }),
    ).toBeVisible();
  });
});
