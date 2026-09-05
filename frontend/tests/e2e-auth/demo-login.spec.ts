import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/setup-status", (route) =>
    route.fulfill({
      json: { needs_setup: false, registration_enabled: false },
    }),
  );
});

for (const [role, title] of [
  ["teacher", "教师演示"],
  ["student", "学生演示"],
] as const) {
  test(`${title}静默登录，不填入凭据并重新进入工作区`, async ({ page }) => {
    let payload: unknown;
    let finishLogin!: () => void;
    const pending = new Promise<void>((resolve) => {
      finishLogin = resolve;
    });
    await page.route("**/api/v1/auth/login/demo", async (route) => {
      payload = route.request().postDataJSON();
      await pending;
      await route.fulfill({ json: { expires_in: 86400, needs_setup: false } });
    });
    // 工作区导航单独拦截；真实身份分流由后端会话测试及工作区现有逻辑覆盖。
    await page.route("**/workspace", (route) =>
      route.fulfill({ contentType: "text/html", body: "<h1>工作区</h1>" }),
    );
    await page.goto("/login?next=/workspace/other-role");
    await page.locator("#email").fill("my@example.com");
    await page.locator("#password").fill("my-own-password");
    await page.getByRole("checkbox").uncheck();
    const storage = await page.evaluate(() => JSON.stringify(localStorage));
    await page.getByRole("button", { name: title, exact: true }).click();
    await expect.poll(() => payload).toEqual({ role, remember_me: false });
    await expect(page.locator("#email")).toHaveValue("my@example.com");
    await expect(page.locator("#password")).toHaveValue("my-own-password");
    await expect(
      page.getByRole("button", { name: "教师演示", exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "学生演示", exact: true }),
    ).toBeDisabled();
    expect(await page.evaluate(() => JSON.stringify(localStorage))).toBe(
      storage,
    );
    finishLogin();
    await expect(page).toHaveURL(/\/workspace$/);
  });
}

test("演示失败可重试，空邮箱密码不阻挡演示入口", async ({ page }) => {
  let count = 0;
  await page.route("**/api/v1/auth/login/demo", (route) => {
    count += 1;
    return route.fulfill({ status: 503, json: { detail: "体验账号暂不可用" } });
  });
  await page.goto("/login");
  await page.getByRole("button", { name: "教师演示", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toHaveText("体验账号暂不可用");
  await expect(page.locator("#email")).toBeEmpty();
  await expect(page.locator("#password")).toBeEmpty();
  await page.getByRole("button", { name: "学生演示", exact: true }).click();
  await expect.poll(() => count).toBe(2);
});

test("登录表单位于演示卡片上方，移动端无横向溢出", async ({ page }) => {
  await page.goto("/login");
  const form = await page.locator("form").boundingBox();
  const demo = await page
    .getByRole("button", { name: "教师演示", exact: true })
    .boundingBox();
  expect(demo!.y).toBeGreaterThan(form!.y + form!.height);
  await page.screenshot({
    path: "test-results/demo-login-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    375,
  );
  await page.screenshot({
    path: "test-results/demo-login-mobile.png",
    fullPage: true,
  });
});

test("原引导页与根路径直接进入登录页", async ({ page }) => {
  await page.goto("/welcome");
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});
