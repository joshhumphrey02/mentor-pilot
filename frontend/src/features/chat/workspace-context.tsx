import { createContext, useContext } from 'react'

/**
 * What interactive blocks need from the workspace they are shown in: which
 * project they belong to, and a way to speak for the learner (tapping
 * "Choose this" on an idea card sends a message, exactly as typing it would).
 */
export interface WorkspaceValue {
  projectId: string
  currentStage: string
  send: (text: string) => void
  /** True while the mentor is replying: buttons that send should wait. */
  busy: boolean
}

export const WorkspaceContext = createContext<WorkspaceValue | null>(null)

/** Null when a block is rendered outside a workspace (a saved item, a preview). */
export const useWorkspace = () => useContext(WorkspaceContext)
