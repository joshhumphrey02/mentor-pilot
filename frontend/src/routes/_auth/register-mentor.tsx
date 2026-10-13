import { useMutation } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'

import { FormAlert, PasswordField, TextField } from '@/components/form/fields'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { AuthShell, linkClass } from '@/features/auth/components/auth-shell'
import { CheckInbox } from '@/features/auth/components/check-inbox'
import { requireGuest } from '@/features/auth/guards'
import type { HelpType } from '@/features/mentoring/api'
import { HelpTypePicker } from '@/features/mentoring/help-type-picker'
import { api } from '@/lib/api/client'
import { errorMessage, unwrap } from '@/lib/api/errors'

export const Route = createFileRoute('/_auth/register-mentor')({
  beforeLoad: requireGuest,
  component: RegisterMentorPage,
})

function RegisterMentorPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [organisation, setOrganisation] = useState('')
  const [province, setProvince] = useState('Western Cape')
  const [expertise, setExpertise] = useState<HelpType[]>([])
  const [accepted, setAccepted] = useState(false)
  const signUp = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/mentors/register', {
          body: {
            full_name: name.trim(),
            email: email.trim(),
            password,
            organisation: organisation.trim(),
            expertise,
            regions: [province],
            availability: '',
            offers: '',
            bio: '',
            accept_privacy: true,
          },
        }),
      ),
  })
  const ready =
    name.trim() && email.includes('@') && password.length >= 8 && expertise.length > 0 && accepted

  if (signUp.isSuccess) {
    return (
      <AuthShell title="Check your inbox" subtitle="Confirm your email, then complete your profile.">
        <CheckInbox email={email} />
        <p className="mt-4 text-sm text-muted-foreground">
          Because mentors work with school learners, an admin reviews every mentor before they
          can see requests. We'll be in touch.
        </p>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title="Become a mentor"
      subtitle="Help a learner turn a design into something real."
      footer={
        <>
          Are you a learner?{' '}
          <Link to="/register" className={linkClass}>
            Sign up here
          </Link>
        </>
      }
    >
      <form
        noValidate
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (ready) signUp.mutate()
        }}
      >
        {signUp.error && <FormAlert>{errorMessage(signUp.error)}</FormAlert>}
        <TextField label="Your name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          autoCapitalize="none"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <PasswordField
          label="Password"
          autoComplete="new-password"
          hint="At least 8 characters."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <TextField
          label="Organisation (optional)"
          value={organisation}
          onChange={(e) => setOrganisation(e.target.value)}
        />
        <TextField label="Province you can help in" value={province} onChange={(e) => setProvince(e.target.value)} />
        <HelpTypePicker legend="What can you help with?" value={expertise} onChange={setExpertise} />
        <label className="flex items-start gap-3 text-sm">
          <Checkbox
            checked={accepted}
            onCheckedChange={(checked) => setAccepted(checked === true)}
            className="mt-0.5 size-5"
          />
          <span>
            I agree to the{' '}
            <Link to="/privacy" target="_blank" className={linkClass}>
              privacy notice
            </Link>
            , and to keep all contact with learners on Mentor Pilot.
          </span>
        </label>
        <Button type="submit" size="touch" disabled={!ready || signUp.isPending} className="mt-2 w-full">
          {signUp.isPending ? 'Creating your account…' : 'Apply to mentor'}
        </Button>
      </form>
    </AuthShell>
  )
}
