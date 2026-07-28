import {Workspace} from "@/views/workspace";
import {Toaster} from "@/components/ui/sonner.jsx";

/**
 * App shell. The whole UI is the resizable workspace.
 *
 * Provider wiring (CopilotKit + mobx store) lives in main.jsx/providers.jsx.
 */
export default function App() {
    return (
        <>
            <Workspace/>
            <Toaster/>
        </>
    );
}
