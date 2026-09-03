import "@/styles/globals.css";

import { type Metadata } from "next";

import { ThemeProvider } from "@/components/theme-provider";
import { DEFAULT_LOCALE } from "@/core/i18n/locale";

// 品牌化(003):站点标题/描述替换为"智能作业批改",去 DeerFlow 产品名。
export const metadata: Metadata = {
  title: "智能作业批改",
  description: "教师智能助手——让每一份作业都被看见。",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang={DEFAULT_LOCALE}
      suppressContentEditableWarning
      suppressHydrationWarning
    >
      <body>
        <ThemeProvider attribute="class" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
