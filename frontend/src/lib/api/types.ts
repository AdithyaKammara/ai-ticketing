import type { components } from './schema'

type S = components['schemas']

export type Me = S['MeOut']
export type Role = S['Role']
export type Availability = S['Availability']
export type TokenOut = S['TokenOut']
export type TicketSummary = S['TicketSummaryOut']
export type TicketDetail = S['TicketOut']
export type TicketCreated = S['TicketCreatedOut']
export type TicketStatus = S['TicketStatus']
export type TriageStatus = S['TriageStatus']
export type Severity = S['Severity']
export type Category = S['Category']
export type TicketEvent = S['EventOut']
export type UserOut = S['UserOut']
export type DepartmentOut = S['DepartmentOut']
export type SkillOut = S['SkillOut']
export type CategoryOut = S['CategoryOut']
export type Summary = S['SummaryOut']
export type VolumePoint = S['VolumePoint']
export type BreakdownBucket = S['BreakdownBucket']
export type AiQuality = S['AiQualityOut']
// Errors aren't modeled in the OpenAPI schema; this matches the backend's one error shape.
export type ApiError = {
  error: { code: string; message: string; details: Record<string, unknown> }
  request_id?: string
}
