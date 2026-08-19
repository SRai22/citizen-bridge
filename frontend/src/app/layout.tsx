import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Citizen Bridge",
  description: "Your agent across all Indian public services",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
