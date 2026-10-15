<<<<<<< HEAD
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
=======
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
  {
    variants: {
      variant: {
        default:
<<<<<<< HEAD
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
=======
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
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
<<<<<<< HEAD
)
=======
);
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
<<<<<<< HEAD
  )
}

export { Badge, badgeVariants }
=======
  );
}

export { Badge, badgeVariants };
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
