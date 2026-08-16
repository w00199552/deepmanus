import Axios from "axios";
import {toast} from "sonner";

const axios = Axios.create({
    baseURL: import.meta.env.VITE_BACKEND_URL,
    timeout: 30000,
});

axios.interceptors.response.use(
    (response) => {
        const data = response.data;
        // ApiResponse / ApiListResponse 的业务失败（HTTP 200 + error 字段）
        // 统一在这里转成异常，让 Store 的 catch 路径一致。
        if (data && data.error && data.error.message) {
            toast.error(data.error.message);
            return Promise.reject(new Error(data.error.message));
        }
        return data;
    },
    (error) => {
        const msg = error.response?.data?.error?.message
            || error.response?.data?.detail
            || error.response?.data?.message
            || error.message
            || "Network error";

        toast.error(msg);
        return Promise.reject(error);
    }
);

export default axios;
