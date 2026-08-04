import type { Metadata } from "next";
import { Geist, Geist_Mono, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AmbientBackground } from "@/components/layout/ambient-background";
import "./globals.css";
import { cn } from "@/lib/utils";

const jetbrainsMono = JetBrains_Mono({subsets:['latin'],variable:'--font-mono'});

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://sentinel-audit.co"),
  title: {
    default: "SENTINEL — Adversarial AI Court for Police Bodycam",
    template: "%s · SENTINEL",
  },
  description:
    "An adversarial review layer for bodycam evidence. Prosecution, Defense and Judge agents on different model families produce a verdict traceable to the exact utterance and video frame. Four jurisdictions.",
  authors: [{ name: "Vitalii Karasov", url: "https://karasov.co" }],
  creator: "Vitalii Karasov",
  verification: {
    google: '<meta name="google-site-verification" content="vNlrEenP6E_iwxlIfDTmm4DQzacAcqUyJgbJPLsclx0" />',
  },
  openGraph: {
    type: "website",
    url: "https://sentinel-audit.co",
    siteName: "SENTINEL",
    title: "SENTINEL — Adversarial AI Court for Police Bodycam",
    description:
      "Three reasoning passes, two opposing model families, one defensible verdict — cited to the exact second of the recording.",
  },
  twitter: {
    card: "summary_large_image",
    title: "SENTINEL — Adversarial AI Court for Police Bodycam",
    description:
      "Three reasoning passes, two opposing model families, one defensible verdict — cited to the exact second.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn("h-full", "antialiased", geistSans.variable, geistMono.variable, "font-mono", jetbrainsMono.variable)}
    >
      <body className="bg-black text-slate-100 antialiased min-h-screen">
        <AmbientBackground />
        <div className="relative z-10 flex flex-col min-h-screen">
          <TooltipProvider delayDuration={300}>
            {children}
          </TooltipProvider>
        </div>
      </body>
    </html>
  );
}
