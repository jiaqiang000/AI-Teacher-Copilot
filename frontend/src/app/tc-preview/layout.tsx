// Teacher Copilot 预览页独立布局(不带 DeerFlow AuthProvider/I18nProvider,
// 保证 use client 页面在无认证环境正常水合;演示专用,真实产品走 workspace 认证)
export default function TcPreviewLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {children}
    </div>
  )
}
