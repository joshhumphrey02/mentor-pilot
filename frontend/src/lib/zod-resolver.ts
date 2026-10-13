import type { FieldErrors, FieldValues, Resolver } from 'react-hook-form'
import type { z } from 'zod'

/**
 * Connects a zod schema to react-hook-form.
 *
 * Written here rather than taken from @hookform/resolvers because that package's
 * optional peers pin zod 3, which conflicts with the zod 4 the router needs.
 * Field paths are flat ("email"), which is all our forms use.
 */
export function zodResolver<Input extends FieldValues, Output>(
  schema: z.ZodType<Output, Input>,
): Resolver<Input, unknown, Output> {
  return async (values) => {
    const result = await schema.safeParseAsync(values)
    if (result.success) return { values: result.data, errors: {} }

    const errors: Record<string, { type: string; message: string }> = {}
    for (const issue of result.error.issues) {
      const path = issue.path.join('.')
      errors[path] ??= { type: issue.code, message: issue.message }
    }
    return { values: {}, errors: errors as FieldErrors<Input> }
  }
}
