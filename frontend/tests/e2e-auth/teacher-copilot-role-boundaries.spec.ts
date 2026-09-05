import { expect, test } from "@playwright/test";

const TEACHER_ROUTES = [
  "/workspace/teacher-copilot/dashboard",
  "/workspace/teacher-copilot/classes",
  "/workspace/teacher-copilot/classes/class_03",
  "/workspace/teacher-copilot/homeworks",
  "/workspace/teacher-copilot/homeworks/new/authoring",
  "/workspace/teacher-copilot/homeworks/hw_004/analysis?class_id=class_03",
  "/workspace/teacher-copilot/students/stu_003",
  "/workspace/agents/teacher-copilot/chats/new",
];

test("学生会话访问所有教师页面都回到学生作业页并提示无权限", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "学生演示", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });

  for (const route of TEACHER_ROUTES) {
    await page.goto(route);
    await expect(page).toHaveURL(
      /\/workspace\/teacher-copilot\/student\/homework\?denied=1$/,
      { timeout: 15_000 },
    );
    await expect(page.getByText("无权限")).toBeVisible({ timeout: 5_000 });
  }
});

test("教师会话访问学生作业页和批改页都回到教师工作台并提示无权限", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "教师演示", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });

  for (const route of [
    "/workspace/teacher-copilot/student/homework",
    "/workspace/teacher-copilot/student/grading?homework_id=hw_004&question_id=q001",
  ]) {
    await page.goto(route);
    await expect(page).toHaveURL(
      /\/workspace\/teacher-copilot\/dashboard\?denied=student$/,
      { timeout: 15_000 },
    );
    await expect(page.getByText("无权限")).toBeVisible({ timeout: 5_000 });
  }
});
