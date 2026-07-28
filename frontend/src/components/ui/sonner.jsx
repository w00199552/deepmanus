import {useTheme} from "@/hooks/use-theme.js";
import {Toaster as Sonner} from "sonner";

/*
 * Toaster — styled to match the old agents Toast: accent-tinted pill with glow
 * for success, destructive for error. Replaces sonner's default muted card so
 * notifications read as deliberate, on-brand alerts.
 */
const Toaster = ({...props}) => {
    const {isDark} = useTheme();

    return (
        <Sonner
            theme={isDark ? "dark" : "light"}
            position="top-right"
            // sit below the 56px (h-14) draggable titlebar so it doesn't overlap
            // the window controls (minimize / maximize / close) in Electron.
            // move the ✕ to the top-right (sonner defaults it to the top-left,
            // which reads oddly when the toast itself is in the top-right corner).
            style={{
                top: "68px",
                "--toast-close-button-start": "unset",
                "--toast-close-button-end": "0",
                "--toast-close-button-transform": "translate(35%, -35%)",
            }}
            // show a ✕ on each toast for manual dismiss
            closeButton
            // click the toast body to dismiss (in addition to the ✕)
            closeOnClick
            toastOptions={{
                unstyled: false,
                classNames: {
                    // base: pill shape, raised, fade-in (anim-rise defined in index.css)
                    toast:
                        "group !rounded-full !px-4 !py-2.5 !text-[13px] !shadow-lg anim-rise !border-transparent",
                    // success → accent green w/ glow (accent-glow defined in index.css)
                    success:
                        "!bg-accent/15 !text-accent accent-glow",
                    // error → destructive red
                    error:
                        "!bg-destructive/15 !text-destructive",
                    description: "!text-current !opacity-80",
                    actionButton:
                        "!bg-accent !text-accent-foreground !rounded-full",
                    cancelButton:
                        "!bg-muted !text-muted-foreground !rounded-full",
                    // keep icons tinted to the toast type color
                    successIcon: "!text-accent",
                    errorIcon: "!text-destructive",
                    // the ✕ button: inherit the toast's text color so it stays
                    // readable on the accent / destructive tinted background
                    closeButton: "!text-current !opacity-60 hover:!opacity-100",
                },
            }}
            {...props}
        />
    );
};

export {Toaster};
