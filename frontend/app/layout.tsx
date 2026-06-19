import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Elixir AI Service Desk',
  description: 'Enterprise AI Service Desk Assistant',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
