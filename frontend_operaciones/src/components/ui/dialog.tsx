<<<<<<< HEAD
"use client"

import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

const Dialog = DialogPrimitive.Root

const DialogTrigger = DialogPrimitive.Trigger

const DialogPortal = DialogPrimitive.Portal

const DialogClose = DialogPrimitive.Close
=======
"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;
const DialogClose = DialogPrimitive.Close;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
=======
      "fixed inset-0 z-50 bg-black/80 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName
=======
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
<<<<<<< HEAD
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
=======
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-border bg-card p-6 shadow-2xl duration-200 sm:rounded-2xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
        className
      )}
      {...props}
    >
      {children}
<<<<<<< HEAD
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitive.Content.displayName
=======
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-xl p-1.5 opacity-70 ring-offset-background transition-opacity hover:opacity-100 hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none cursor-pointer">
        <X className="h-4 w-4" />
        <span className="sr-only">Cerrar</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
<<<<<<< HEAD
      "flex flex-col space-y-1.5 text-center sm:text-left",
=======
      "flex flex-col space-y-1.5 text-center sm:text-left border-b border-border pb-4",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
)
DialogHeader.displayName = "DialogHeader"
=======
);
DialogHeader.displayName = "DialogHeader";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
<<<<<<< HEAD
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
=======
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 border-t border-border pt-4",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
)
DialogFooter.displayName = "DialogFooter"
=======
);
DialogFooter.displayName = "DialogFooter";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "text-lg font-semibold leading-none tracking-tight",
=======
      "text-lg font-bold leading-none tracking-tight text-foreground flex items-center gap-2",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
DialogTitle.displayName = DialogPrimitive.Title.displayName
=======
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
<<<<<<< HEAD
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
DialogDescription.displayName = DialogPrimitive.Description.displayName
=======
    className={cn("text-xs text-muted-foreground", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
<<<<<<< HEAD
  DialogClose,
  DialogTrigger,
=======
  DialogTrigger,
  DialogClose,
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
<<<<<<< HEAD
}
=======
};
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
