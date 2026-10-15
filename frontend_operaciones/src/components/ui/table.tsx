<<<<<<< HEAD
import * as React from "react"

import { cn } from "@/lib/utils"
=======
import * as React from "react";
import { cn } from "@/lib/utils";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
<<<<<<< HEAD
  <div className="relative w-full overflow-auto">
=======
  <div className="relative w-full overflow-auto rounded-xl border border-border">
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
<<<<<<< HEAD
))
Table.displayName = "Table"
=======
));
Table.displayName = "Table";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
<<<<<<< HEAD
  <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
))
TableHeader.displayName = "TableHeader"
=======
  <thead ref={ref} className={cn("[&_tr]:border-b bg-muted/40", className)} {...props} />
));
TableHeader.displayName = "TableHeader";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
<<<<<<< HEAD
))
TableBody.displayName = "TableBody"
=======
));
TableBody.displayName = "TableBody";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TableFooter = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn(
      "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
TableFooter.displayName = "TableFooter"
=======
));
TableFooter.displayName = "TableFooter";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
=======
      "border-b border-border transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
TableRow.displayName = "TableRow"
=======
));
TableRow.displayName = "TableRow";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
<<<<<<< HEAD
      "h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0",
=======
      "h-12 px-4 text-left align-middle font-bold text-muted-foreground text-xs uppercase tracking-wider [&:has([role=checkbox])]:pr-0",
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
      className
    )}
    {...props}
  />
<<<<<<< HEAD
))
TableHead.displayName = "TableHead"
=======
));
TableHead.displayName = "TableHead";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0", className)}
    {...props}
  />
<<<<<<< HEAD
))
TableCell.displayName = "TableCell"

const TableCaption = React.forwardRef<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-muted-foreground", className)}
    {...props}
  />
))
TableCaption.displayName = "TableCaption"
=======
));
TableCell.displayName = "TableCell";
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
<<<<<<< HEAD
  TableCaption,
}
=======
};
>>>>>>> 8f5a0df8ff1673f90c3529ee33ea984536c24aee
