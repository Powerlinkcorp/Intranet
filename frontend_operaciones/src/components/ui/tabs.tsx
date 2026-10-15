<<<<<<< HEAD
import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"

import { cn } from "@/lib/utils"

const Tabs = TabsPrimitive.Root
=======
import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground",
=======
      "inline-flex h-10 items-center justify-center rounded-xl bg-muted/60 p-1 text-muted-foreground border border-border",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
TabsList.displayName = TabsPrimitive.List.displayName
=======
));
TabsList.displayName = TabsPrimitive.List.displayName;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
=======
      "inline-flex items-center justify-center whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-bold ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm cursor-pointer",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName
=======
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
=======
      "mt-3 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
=======
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
