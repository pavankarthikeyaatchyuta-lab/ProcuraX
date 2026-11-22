import "./design.css";
import type { Metadata } from "next";
import {WorkspaceProvider} from '../components/workspace';
import Background from '../components/Background';
export const metadata: Metadata = {
  title: "ProcuraX — AI Procurement Intelligence Platform for MSMEs",
  description: "Procurement, made intelligent. Know what to buy, when to buy, how much to buy and where to buy.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body><Background><WorkspaceProvider>{children}</WorkspaceProvider></Background></body>
    </html>
  );
}
