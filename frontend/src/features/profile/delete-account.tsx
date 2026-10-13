import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { toast } from 'sonner'

import { FormAlert, PasswordField, TextField } from '@/components/form/fields'
import { ResponsiveDialog } from '@/components/responsive-dialog'
import { Button } from '@/components/ui/button'
import { useDeleteAccount, useUser } from '@/features/auth/api'
import { errorMessage } from '@/lib/api/errors'

const CONFIRM_WORD = 'DELETE'

export function DeleteAccount() {
  const user = useUser()
  const navigate = useNavigate()
  const remove = useDeleteAccount()
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState('')
  const [password, setPassword] = useState('')

  const ready = confirm === CONFIRM_WORD && (!user.has_password || password.length > 0)

  const onOpenChange = (next: boolean) => {
    setOpen(next)
    if (!next) {
      setConfirm('')
      setPassword('')
      remove.reset()
    }
  }

  return (
    <>
      <Button variant="destructive" size="touch" onClick={() => setOpen(true)}>
        Delete my account
      </Button>
      <ResponsiveDialog
        open={open}
        onOpenChange={onOpenChange}
        title="Delete your account?"
        description="This permanently erases your profile and your projects. It can't be undone."
      >
        <form
          className="grid gap-4"
          onSubmit={async (event) => {
            event.preventDefault()
            if (!ready) return
            const done = await remove
              .mutateAsync({ confirm: CONFIRM_WORD, password: user.has_password ? password : null })
              .then(() => true)
              .catch(() => false)
            if (done) {
              toast.success('Your account has been deleted.')
              await navigate({ to: '/' })
            }
          }}
        >
          {remove.error && <FormAlert>{errorMessage(remove.error)}</FormAlert>}
          {user.has_password && (
            <PasswordField
              label="Your password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
          <TextField
            label={`Type ${CONFIRM_WORD} to confirm`}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value.toUpperCase())}
          />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" size="touch" onClick={() => onOpenChange(false)}>
              Keep my account
            </Button>
            <Button
              type="submit"
              size="touch"
              disabled={!ready || remove.isPending}
              className="bg-danger text-background hover:bg-danger/90"
            >
              {remove.isPending ? 'Deleting…' : 'Delete forever'}
            </Button>
          </div>
        </form>
      </ResponsiveDialog>
    </>
  )
}
