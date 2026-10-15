import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground font-bold shadow-sm",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        destructive:
          "border-transparent bg-destructive/20 text-destructive border-destructive/30",
        outline: "text-foreground border-border",
        success:
          "border-emerald-500/30 bg-emerald-500/15 text-emerald-400 font-medium",
        warning:
          "border-amber-500/30 bg-amber-500/15 text-amber-400 font-medium",
        info:
          "border-blue-500/30 bg-blue-500/15 text-blue-400 font-medium",
        gold:
          "border-primary/40 bg-primary/15 text-primary font-bold",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
