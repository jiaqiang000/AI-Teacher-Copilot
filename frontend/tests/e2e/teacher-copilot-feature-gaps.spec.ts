import { expect, test, type Page } from "@playwright/test";

async function mockTeacherApis(page: Page) {
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
});
