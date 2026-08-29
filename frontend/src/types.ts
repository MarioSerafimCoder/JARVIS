import type { ReactNode } from 'react'

export type Page = 'now' | 'chat' | 'memory' | 'library' | 'tasks' | 'calendar' | 'automations' | 'connections' | 'persona' | 'devices' | 'activity' | 'usage' | 'settings'
export type NavItem = [Page, string, ReactNode]

export interface Conversation { id: string; title: string; created_at: string; updated_at: string }
export interface Message { id: string; role: 'user' | 'assistant' | 'system' | 'tool' | 'error'; content: string; created_at?: string; generation_status?: 'complete' | 'cancelled'; context?: ContextEvidence }
export interface Memory { id: string; content: string; category: string; importance: number; source_type: string; source_reference?: string; created_at: string; updated_at: string; last_used_at?: string }
export interface Task { id: string; title: string; description: string; status: 'inbox' | 'planned' | 'doing' | 'done' | 'cancelled'; priority: 'low' | 'normal' | 'high' | 'critical'; due_at?: string; project?: string; estimated_minutes?: number; updated_at: string }
export interface DocumentItem { id: string; filename: string; original_name: string; type: string; status: string; chunk_count: number; size_bytes: number }
export interface ContextDocument { document_id: string; filename: string; location?: string; relevant_text: string; score?: number }
export interface ContextEvidence { memories?: Memory[]; documents?: ContextDocument[]; tasks?: Task[]; actions?: ToolAction[]; budget?: { max_chars: number; used_chars: number; estimated_tokens: number } }
export interface ToolAction { action_id: string; tool: string; input: Record<string, unknown>; status: string; id?: string; conversation_id?: string; created_at?: string }
export interface ActivityItem { id: string; tool: string; status: string; timestamp: string; input: Record<string, unknown>; result: Record<string, unknown> }
export interface SearchItem { type: string; id: string; title: string; subtitle?: string }
export interface Health { status: string; llm: { status?: string; model?: string; error?: string } }
export interface ChatResult { conversation_id: string; message: string; context: ContextEvidence; actions: ToolAction[] }
export interface StreamEvent { type: 'start' | 'token' | 'action' | 'done' | 'error'; conversation_id?: string; content?: string; message?: string; context?: ContextEvidence; action?: ToolAction; actions?: ToolAction[]; error?: { code: string; message: string } }
