import { api, unwrap } from "@/services/api";
import type { DatabaseConnection, DBEngine, SchemaInfo } from "@/types/api";

export interface ConnectionCreatePayload {
  name: string;
  engine: DBEngine;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  file_path?: string;
  extra_params?: string;
  read_only?: boolean;
}

export const connectionsService = {
  list() {
    return unwrap<DatabaseConnection[]>(api.get("/connections"));
  },
  create(payload: ConnectionCreatePayload) {
    return unwrap<DatabaseConnection>(api.post("/connections", payload));
  },
  test(connectionId: string) {
    return unwrap<{ success: boolean; message: string }>(api.post(`/connections/${connectionId}/test`));
  },
  remove(connectionId: string) {
    return unwrap<null>(api.delete(`/connections/${connectionId}`));
  },
  schema(connectionId: string, refresh = false) {
    return unwrap<SchemaInfo>(api.get(`/connections/${connectionId}/schema`, { params: { refresh } }));
  },
};
