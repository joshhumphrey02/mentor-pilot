/**
 * The Unsplash photos used on the public pages. They are served straight from
 * Unsplash's image CDN, which resizes and re-encodes on request, so a phone
 * never downloads a desktop-sized file.
 */
export interface Photo {
  /** The part after `photo-` in an images.unsplash.com URL. */
  id: string
  alt: string
  /** The photographer, credited in the page footer. */
  by: string
}

const photo = (id: string, alt: string, by: string): Photo => ({ id, alt, by })

export const PHOTOS = {
  makerspace: photo(
    '1705579608049-a251d1ba0405',
    'A young engineer wiring up a project at a workbench',
    'ThisisEngineering',
  ),
  teamBuild: photo(
    '1596496050860-b48b170fc584',
    'Two students fitting a part to a vehicle they built',
    'Jeswin Thomas',
  ),
  breadboardHands: photo(
    '1596496181935-7801d2065877',
    'Hands pushing jumper wires into a breadboard',
    'Jeswin Thomas',
  ),
  classroomReader: photo(
    '1632215861513-130b66fe97f4',
    'A learner reading aloud in a full classroom',
    'Emmanuel Ikwuegbu',
  ),
  breadboardBuild: photo(
    '1596496181848-3091d4878b24',
    'A student building a circuit on a breadboard',
    'Jeswin Thomas',
  ),
  learnerLaptop: photo(
    '1620829813573-7c9e1877706f',
    'A learner working on a laptop',
    'Kojo Kwarteng',
  ),
  learnerNotes: photo(
    '1622295023825-6e319464b810',
    'A learner checking notes beside a laptop',
    'Emmanuel Ikwuegbu',
  ),
  classroom: photo(
    '1567057419565-4349c49d8a04',
    'Learners at their desks in a classroom',
    'Annie Spratt',
  ),
  mentoring: photo(
    '1705579608086-cf18dee3f1a8',
    'A mentor talking a student through a 3D design on a laptop',
    'ThisisEngineering',
  ),
  soldering: photo(
    '1581090466619-e945d2e2980e',
    'An engineer soldering at a workbench',
    'ThisisEngineering',
  ),
  arduino: photo(
    '1634454023167-59d99c0921a5',
    'A microcontroller board beside a breadboard',
    'Vishnu Mohanan',
  ),
  breadboardDark: photo(
    '1634452015397-ad0686a2ae2d',
    'A breadboard circuit with colourful jumper wires',
    'Vishnu Mohanan',
  ),
  // One per pathway stage, in order.
  stageProblem: photo(
    '1526378787940-576a539ba69d',
    'A pinboard of photos and sticky notes about a neighbourhood',
    'Jo Szczepanska',
  ),
  stageIdeas: photo(
    '1586936893354-362ad6ae47ba',
    'Hands sorting sticky notes with ideas on them',
    'UX Indonesia',
  ),
  stageQuestion: photo(
    '1579017308347-e53e0d2fc5e9',
    'Someone writing in a notebook',
    'Marcos Paulo Prado',
  ),
  stageMethod: photo(
    '1554475901-4538ddfbccc2',
    'Hands holding laboratory flasks of coloured liquid',
    'Alex',
  ),
  stageTools: photo(
    '1710770563074-6d9cc0d3e338',
    'Someone writing code on a laptop',
    'Ibrahim Yusuf',
  ),
  stagePrototype: photo(
    '1631378297854-185cff6b0986',
    'A microcontroller wired to a breadboard',
    'Vishnu Mohanan',
  ),
  stageData: photo(
    '1763038311036-6d18805537e5',
    'Charts and graphs on a laptop screen',
    'Apex Virtual Education',
  ),
  stageCommunication: photo(
    '1712903911017-7c10a3c4b3e5',
    'A presenter pointing at a display board',
    'Walls.io',
  ),
  stageExpo: photo(
    '1646579886135-068c73800308',
    'A student presenting to an audience',
    'Herlambang Tinasih Gusti',
  ),
} satisfies Record<string, Photo>

const WIDTHS = [480, 800, 1200, 1800]

/** A URL for the photo at `width` CSS pixels wide, in the best format the browser accepts. */
export function photoUrl(photo: Photo, width: number): string {
  return `https://images.unsplash.com/photo-${photo.id}?auto=format&fit=crop&q=70&w=${width}`
}

export function photoSrcSet(photo: Photo): string {
  return WIDTHS.map((width) => `${photoUrl(photo, width)} ${width}w`).join(', ')
}

/** Everyone whose photos appear, once each, for the credit line. */
export const PHOTOGRAPHERS = [...new Set(Object.values(PHOTOS).map((item) => item.by))].sort()
