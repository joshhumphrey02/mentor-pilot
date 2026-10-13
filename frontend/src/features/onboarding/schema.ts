import { z } from 'zod'

import { emailSchema, nameSchema } from '@/features/auth/schemas'

import { ageFrom, isMinor, LEARNING_STYLES } from './options'

export type LearningStyle = (typeof LEARNING_STYLES)[number]['value']

const isLearningStyle = (value: string): value is LearningStyle =>
  LEARNING_STYLES.some((style) => style.value === value)

/**
 * The whole multi-step form as one schema.
 *
 * The object itself only fixes the shape; every rule lives in `superRefine`.
 * That is deliberate: zod skips object-level refinements when any field fails
 * its own check, so a later step's empty field (say, no interests yet) would
 * silently switch off the guardian rules on step one.
 */
export const onboardingSchema = z
  .object({
    full_name: z.string(),
    date_of_birth: z.string(),
    guardian_email: z.string(),
    guardian_consent: z.boolean(),

    // 'search': picked from results. 'new': typed in. 'none': not at a school.
    school_mode: z.enum(['search', 'new', 'none']),
    school_id: z.string().nullable(),
    school_name: z.string(),
    school_town: z.string(),
    province: z.string(),
    grade: z.string(),

    interests: z.array(z.string()),
    learning_style: z.string(),
    preferred_language: z.enum(['en', 'af', 'xh']),
    accept_privacy: z.boolean(),
    needs_privacy: z.boolean(),
  })
  .superRefine((values, ctx) => {
    const fail = (path: keyof typeof values, message: string) =>
      ctx.addIssue({ code: 'custom', path: [path], message })

    const name = nameSchema.safeParse(values.full_name)
    if (!name.success) fail('full_name', name.error.issues[0]?.message ?? 'Enter your name.')

    const age = ageFrom(values.date_of_birth)
    if (!values.date_of_birth) fail('date_of_birth', 'Enter your date of birth.')
    else if (age === null || age < 8 || age > 100) {
      fail('date_of_birth', 'Please check your date of birth.')
    }

    if (isMinor(values.date_of_birth)) {
      if (!emailSchema.safeParse(values.guardian_email).success) {
        fail('guardian_email', 'Enter the email of a parent, guardian or teacher.')
      }
      if (!values.guardian_consent) {
        fail('guardian_consent', 'Please ask them first, then tick this box.')
      }
    }

    if (values.school_mode === 'search' && !values.school_id) {
      fail('school_id', 'Choose your school, or add it if it isn’t listed.')
    }
    if (values.school_mode === 'new' && values.school_name.trim().length < 2) {
      fail('school_name', 'Enter your school’s name.')
    }
    if (!values.province) fail('province', 'Choose your province.')

    if (values.interests.length === 0) fail('interests', 'Pick at least one.')
    if (!isLearningStyle(values.learning_style)) {
      fail('learning_style', 'Choose the one that fits you best.')
    }
    if (values.needs_privacy && !values.accept_privacy) {
      fail('accept_privacy', 'Please accept the privacy notice to continue.')
    }
  })

export type OnboardingValues = z.infer<typeof onboardingSchema>
