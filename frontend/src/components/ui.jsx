// Small styled building blocks (Button, Card, Input, Label, Badge), made with Tailwind classes.
import { cn } from "@/lib";

// --- button ------------------------------------------------------------------------------------

const BUTTON_STYLES = {
  default: "bg-primary text-primary-foreground hover:bg-primary/80",
  outline: "border-border bg-background hover:bg-muted hover:text-foreground",
  ghost: "hover:bg-muted hover:text-foreground",
  link: "text-primary underline-offset-4 hover:underline",
};

const BUTTON_SIZES = {
  default: "h-8 px-2.5",
  sm: "h-7 rounded-md px-2.5 text-[0.8rem]",
};

/** The classes of a button; also used to make a <Link> look like one. */
export function buttonClass(variant = "default", size = "default", className = "") {
  return cn(
    "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-transparent text-sm font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50",
    BUTTON_STYLES[variant],
    BUTTON_SIZES[size],
    className,
  );
}

/** A text link in the app's colour. */
export const linkClass = "text-primary underline-offset-4 hover:underline";

export function Button({ className, variant = "default", size = "default", ...props }) {
  return <button className={buttonClass(variant, size, className)} {...props} />;
}

// --- card --------------------------------------------------------------------------------------

export function Card({ className, ...props }) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex flex-col gap-4 overflow-hidden rounded-xl bg-card py-4 text-sm text-card-foreground ring-1 ring-foreground/10",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("grid auto-rows-min items-start gap-1 px-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }) {
  return <div className={cn("text-base leading-snug font-medium", className)} {...props} />;
}

export function CardDescription({ className, ...props }) {
  return <div className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function CardContent({ className, ...props }) {
  return <div className={cn("px-4", className)} {...props} />;
}

// --- input, select, textarea and label ---------------------------------------------------------

const FIELD_FOCUS =
  "rounded-lg border border-input bg-transparent text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function Select({ className, ...props }) {
  return <select className={cn("h-8 w-full px-2", FIELD_FOCUS, className)} {...props} />;
}

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn("w-full px-2.5 py-1.5 aria-invalid:border-destructive", FIELD_FOCUS, className)}
      {...props}
    />
  );
}

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }) {
  return (
    <label
      className={cn("flex items-center gap-2 text-sm leading-none font-medium select-none", className)}
      {...props}
    />
  );
}

// --- badge -------------------------------------------------------------------------------------

const BADGE_STYLES = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-secondary text-secondary-foreground",
  destructive: "bg-destructive/10 text-destructive",
  outline: "border-border text-foreground",
};

export function Badge({ className, variant = "default", ...props }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-4xl border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        BADGE_STYLES[variant],
        className,
      )}
      {...props}
    />
  );
}
