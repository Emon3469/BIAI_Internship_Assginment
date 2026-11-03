import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BIAI CRM Workspace",
  description: "Enquiry intelligence and corporate lead pipeline workspace"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
