import { errorMessage } from '../settings/llmApi'
import { ApiError } from '../../api'

/** The reason for a failed call, in plain words, for the activity log. */
export const whyFailed = (e: unknown) => (e instanceof ApiError ? errorMessage(e) : e instanceof Error ? e.message : 'Something went wrong.')
