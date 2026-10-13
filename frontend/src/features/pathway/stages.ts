/**
 * The nine-stage project pathway, for marketing and empty states only.
 * Inside the app the stages come from the API (they are editable by admins).
 */
export const PATHWAY_STAGES = [
  { key: 'problem_discovery', title: 'Problem Discovery', summary: 'Find a real problem in your community, school or home.' },
  { key: 'idea_development', title: 'Idea Development', summary: 'Generate and compare project ideas, then pick one.' },
  { key: 'research_question', title: 'Research Question', summary: 'Write a focused, testable question or engineering goal.' },
  { key: 'method', title: 'Method', summary: 'Choose the scientific method or an engineering design process.' },
  { key: 'ai_digital_tools', title: 'AI and Digital Tools', summary: 'Decide which simulation, coding and data tools to use.' },
  { key: 'design_prototyping', title: 'Design and Prototyping', summary: 'Sketches, schematics, materials and a build plan.' },
  { key: 'testing_analysis', title: 'Testing and Data Analysis', summary: 'Plan trials, record data and chart your results.' },
  { key: 'technical_communication', title: 'Technical Communication', summary: 'Write the report, abstract, poster and logbook.' },
  { key: 'expo_preparation', title: 'Expo Preparation', summary: 'Practise judge questions and finish your display board.' },
] as const

export type StageKey = (typeof PATHWAY_STAGES)[number]['key']

export function stagePosition(key: string): { number: number; title: string } {
  const index = PATHWAY_STAGES.findIndex((stage) => stage.key === key)
  const stage = PATHWAY_STAGES[index] ?? PATHWAY_STAGES[0]
  return { number: Math.max(index, 0) + 1, title: stage.title }
}
