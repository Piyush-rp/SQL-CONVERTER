export type DBEngine = "postgresql" | "mysql" | "mssql" | "sqlite";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "editor" | "viewer";
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DatabaseConnection {
  id: string;
  name: string;
  engine: DBEngine;
  host: string;
  database: string;
  read_only: boolean;
  created_at: string;
}

export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  isPrimaryKey: boolean;
}

export interface ForeignKeyInfo {
  column: string;
  referencesTable: string;
  referencesColumn: string;
}

export interface TableInfo {
  name: string;
  columns: ColumnInfo[];
  primaryKey: string[];
  foreignKeys: ForeignKeyInfo[];
  indexes: { name: string; columns: string[]; unique: boolean }[];
}

export interface SchemaInfo {
  engine: string;
  database: string;
  tables: TableInfo[];
}

export interface ExecutionResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
}

export interface ChartSpec {
  chart_type: "bar" | "line" | "pie" | "table" | "none";
  x_key: string | null;
  y_keys: string[];
  title: string;
  reason: string;
}

export interface OptimizationSuggestion {
  severity: "info" | "warning";
  message: string;
}

export type AskStatus = "success" | "failed" | "rejected" | "clarification_needed";

export interface AskResponse {
  status: AskStatus;
  question: string;
  sql: string | null;
  explanation: string;
  execution: ExecutionResult | null;
  chart_spec: ChartSpec | null;
  optimization_suggestions: OptimizationSuggestion[];
  retry_count: number;
  error_message: string;
}

export interface QueryHistoryEntry {
  id: string;
  question: string;
  generated_sql: string;
  status: "success" | "failed" | "rejected";
  row_count: number;
  execution_time_ms: number;
  created_at: string;
}

export interface APIResponse<T> {
  success: boolean;
  data: T | null;
  error: { code: string; message: string; details: Record<string, unknown> } | null;
  meta: Record<string, unknown>;
}
