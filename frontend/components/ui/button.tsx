import { cn } from "@/lib/utils";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import Link from "next/link";

const variants = {
  primary: "bg-[var(--app-accent-green)] text-[#fbf5e6] hover:brightness-110",
  gold: "bg-[var(--app-accent-gold)] text-[#2b2113] hover:brightness-110",
  ghost: "bg-[var(--app-panel)] text-[var(--app-ink)] hover:bg-[var(--app-panel-alt)]",
  clay: "bg-[var(--app-accent-clay)] text-[#fbf5e6] hover:brightness-110",
};

const sizes = {
  sm: "px-3 py-2 text-[9px]",
  md: "px-5 py-3 text-[10px]",
  lg: "px-7 py-4 text-[12px]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
}

export const PixelButton = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn("pixel-button cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed", variants[variant], sizes[size], className)}
      {...props}
    />
  )
);
PixelButton.displayName = "PixelButton";

export function PixelLinkButton({
  href,
  className,
  variant = "primary",
  size = "md",
  children,
}: {
  href: string;
  className?: string;
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={cn("pixel-button inline-block cursor-pointer text-center", variants[variant], sizes[size], className)}>
      {children}
    </Link>
  );
}
