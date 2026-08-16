import {useContext} from "react";

import {MobxContext, StoreProvider as RootStoreProvider} from "@/stores/index.js";

export function useStore() {
    const context = useContext(MobxContext);
    if (!context) throw new Error("useStore must be used within StoreProvider");
    return context;
}

export const StoreProvider = RootStoreProvider;
