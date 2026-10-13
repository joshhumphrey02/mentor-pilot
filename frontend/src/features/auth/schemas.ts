import { z } from 'zod'

export const emailSchema = z
  .string()
  .trim()
  .min(1, 'Enter your email address.')
  .pipe(z.email('That email address doesn’t look right.'))

// Mirrors the backend: length is the only rule.
export const newPasswordSchema = z
  .string()
  .min(8, 'Use at least 8 characters.')
  .max(128, 'Use at most 128 characters.')

export const nameSchema = z
  .string()
  .trim()
  .min(1, 'Enter your name.')
  .max(120, 'That name is too long.')

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Enter your password.'),
})

export const registerSchema = z.object({
  full_name: nameSchema,
  email: emailSchema,
  password: newPasswordSchema,
  accept_privacy: z.literal(true, 'Please accept the privacy notice to continue.'),
})

export const emailOnlySchema = z.object({ email: emailSchema })

export const resetPasswordSchema = z.object({ password: newPasswordSchema })
