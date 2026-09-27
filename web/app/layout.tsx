import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "AutonomousDev Harness",
  description: "Evidence, state, and control for autonomous coding agents",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
