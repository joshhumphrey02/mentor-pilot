/**
 * The nine-stage project pathway, for marketing and empty states only.
 * Inside the app the stages come from the API (they are editable by admins).
 */
export const PATHWAY_STAGES = [
  { title: 'Problem Discovery', summary: 'Find a real problem in your community, school or home.' },
  { title: 'Idea Development', summary: 'Generate and compare project ideas, then pick one.' },
  { title: 'Research Question', summary: 'Write a focused, testable question or engineering goal.' },
  { title: 'Method', summary: 'Choose the scientific method or an engineering design process.' },
  { title: 'AI and Digital Tools', summary: 'Decide which simulation, coding and data tools to use.' },
  { title: 'Design and Prototyping', summary: 'Sketches, schematics, materials and a build plan.' },
  { title: 'Testing and Data Analysis', summary: 'Plan trials, record data and chart your results.' },
  { title: 'Technical Communication', summary: 'Write the report, abstract, poster and logbook.' },
  { title: 'Expo Preparation', summary: 'Practise judge questions and finish your display board.' },
] as const
