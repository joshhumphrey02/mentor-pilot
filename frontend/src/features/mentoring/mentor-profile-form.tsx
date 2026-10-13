import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { FormAlert, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { PROVINCES } from '@/features/onboarding/options'
import { errorMessage } from '@/lib/api/errors'
import { cn } from '@/lib/utils'

import { type HelpType, mentorProfileQueryOptions, type MentorProfile, useSaveMentorProfile } from './api'
import { HelpTypePicker } from './help-type-picker'

function Form({ profile }: { profile: MentorProfile }) {
  const save = useSaveMentorProfile()
  const [expertise, setExpertise] = useState(profile.expertise as HelpType[])
  const [regions, setRegions] = useState(profile.regions)
  const [organisation, setOrganisation] = useState(profile.organisation)
  const [availability, setAvailability] = useState(profile.availability)
  const [offers, setOffers] = useState(profile.offers)

  return (
    <form
      className="grid gap-5"
      onSubmit={async (event) => {
        event.preventDefault()
        try {
          await save.mutateAsync({ expertise, regions, organisation, availability, offers, bio: profile.bio })
          toast.success('Profile saved')
        } catch (error) {
          toast.error(errorMessage(error))
        }
      }}
    >
      {!profile.is_approved && (
        <FormAlert tone="info">
          Your profile is waiting for approval. Because mentors work with school learners, an
          admin checks every mentor before they can see requests. Fill in your profile so we can
          review it.
        </FormAlert>
      )}
      <HelpTypePicker legend="What can you help with?" value={expertise} onChange={setExpertise} />
      <fieldset>
        <legend className="text-sm font-medium">Where can you help in person?</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {PROVINCES.map((province) => {
            const selected = regions.includes(province)
            return (
              <button
                key={province}
                type="button"
                aria-pressed={selected}
                onClick={() =>
                  setRegions(selected ? regions.filter((r) => r !== province) : [...regions, province])
                }
                className={cn(
                  'min-h-11 rounded-full border px-4 text-sm font-medium',
                  selected ? 'border-primary bg-primary text-primary-foreground' : 'bg-card hover:border-primary',
                )}
              >
                {province}
              </button>
            )
          })}
        </div>
      </fieldset>
      <TextField label="Organisation" value={organisation} onChange={(e) => setOrganisation(e.target.value)} />
      <TextField
        label="When are you available?"
        value={availability}
        onChange={(e) => setAvailability(e.target.value)}
      />
      <TextField
        label="What can you offer?"
        hint="For example: a workshop with tools, spare components, one-on-one coaching."
        value={offers}
        onChange={(e) => setOffers(e.target.value)}
      />
      <Button
        type="submit"
        size="touch"
        disabled={save.isPending || expertise.length === 0 || regions.length === 0}
        className="justify-self-start"
      >
        {save.isPending ? 'Saving…' : 'Save profile'}
      </Button>
    </form>
  )
}

export function MentorProfileForm() {
  const profile = useQuery(mentorProfileQueryOptions)
  if (!profile.data) return <Skeleton className="h-64 rounded-2xl" />
  return <Form profile={profile.data} />
}
