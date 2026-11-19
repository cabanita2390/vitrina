/**
 * Cliente tipado de la API, generado desde el OpenAPI de FastAPI
 * (`npm run gen:api -w apps/web` regenera src/api/schema.d.ts).
 */
import createClient, { type Middleware } from "openapi-fetch";
import { supabase } from "@/lib/supabase";
import type { paths } from "./schema";

const withSupabaseToken: Middleware = {
  async onRequest({ request }) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL });
api.use(withSupabaseToken);
