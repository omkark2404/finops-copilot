import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'finops-copilot — FinOps Decision Platform',
  description: 'Cloud cost analytics, anomaly detection, and optimization recommendations powered by FOCUS billing data.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  )
}
