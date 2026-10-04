import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/layout/NavBar";
import { Footer } from "@/components/layout/Footer";
import { Starfield } from "@/components/layout/Starfield";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { AuthProvider } from "@/lib/AuthContext";

export const metadata: Metadata = {
  title: "AtmoSpy",
  description: "An autonomous scientific investigator that discovers environmental trends in NASA Earth data.",
};

const THEME_INIT_SCRIPT = `
(function() {
  try {
    var stored = localStorage.getItem('etd-theme');
    var theme = stored === 'light' || stored === 'dark' ? stored : (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        {/* Runs before paint to avoid a light/dark flash on load. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col scanline-bg" suppressHydrationWarning>
        <AuthProvider>
          <Starfield />
          <NavBar />
          <main className="flex-1">{children}</main>
          <Footer />
          <CommandPalette />
        </AuthProvider>
      </body>
    </html>
  );
}
