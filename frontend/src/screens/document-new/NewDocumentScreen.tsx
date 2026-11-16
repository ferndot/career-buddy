import { Box, Button, Text } from '@chakra-ui/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toaster } from '../../components'
import { getFit, getPreview, getProfile, getTemplates, SAVED_KEY, saveDocument } from '../documents/api'
import { DetailsStep } from './DetailsStep'
import { JobStep } from './JobStep'
import { ReviewStep } from './ReviewStep'
import { StepIndicator } from './StepIndicator'
import { TemplateStep } from './TemplateStep'
import { buildSave, clearDraft, loadDraft, prefill, saveDraft, type Wizard } from './state'

export function NewDocumentScreen() {
  const navigate = useNavigate()
  const [w, setW] = useState<Wizard>(loadDraft)
  const qc = useQueryClient()
  const set = (patch: Partial<Wizard>) => {
    setW((prev) => ({ ...prev, ...patch }))
  }

  useEffect(() => saveDraft(w), [w]) // the draft saves itself

  const templates = useQuery({ queryKey: ['templates'], queryFn: getTemplates })
  const template = templates.data?.find((t) => t.id === w.templateId)
  useEffect(() => {
    const first = templates.data?.find((t) => t.kind === w.kind)
    if (first && !template) setW((prev) => ({ ...prev, templateId: first.id }))
  }, [templates.data, template, w.kind])

  const onDetails = w.step === 3
  const hasJob = w.jobText.trim().length > 0
  const profile = useQuery({ queryKey: ['profile'], queryFn: getProfile, enabled: w.step >= 3 })
  const fit = useQuery({ queryKey: ['fit', w.jobText], queryFn: () => getFit(w.jobText), enabled: onDetails && hasJob })
  const details = useQuery({
    queryKey: ['details-preview', w.templateId, w.jobText, w.inputs],
    queryFn: () => getPreview({ template: w.templateId, job_text: w.jobText, inputs: w.inputs }),
    enabled: onDetails && !!w.templateId,
  })

  const fitSettled = !hasJob || fit.isSuccess || fit.isError
  useEffect(() => {
    if (onDetails && profile.data && fitSettled && !w.prefilled) {
      setW((prev) => ({ ...prev, ...prefill(profile.data, fit.data?.positions ?? null) }))
    }
  }, [onDetails, profile.data, fit.data, fitSettled, w.prefilled])

  const missingInput = template?.required.some((f) => !w.inputs[f]?.trim()) ?? true
  const canNext = w.step === 1 ? hasJob || w.noJob : w.step === 2 ? !missingInput : w.step === 3 ? w.prefilled : true
  const go = (step: Wizard['step']) => set({ step })

  const save = useMutation({
    mutationFn: () => saveDocument(buildSave(w, template!)),
    onSuccess: (doc) => {
      clearDraft()
      void qc.invalidateQueries({ queryKey: SAVED_KEY })
      toaster.create({ type: 'success', title: 'Document saved', description: doc.label })
      navigate('/documents')
    },
  })
  const next = () => {
    if (w.step < 4) return go((w.step + 1) as Wizard['step'])
    if (template) save.mutate()
  }

  return (
    <>
      <StepIndicator current={w.step} />
      {w.step === 1 && <JobStep w={w} set={set} />}
      {w.step === 2 &&
        (templates.data ? (
          <TemplateStep w={w} templates={templates.data} set={set} />
        ) : (
          <Text color="app.muted">{templates.isError ? 'Could not load templates.' : 'Loading templates...'}</Text>
        ))}
      {w.step === 3 && (
        <DetailsStep
          w={w}
          set={set}
          profile={profile.data}
          tailoring={details.data?.tailoring}
          loading={fit.isLoading || details.isLoading || profile.isLoading}
          failed={profile.isError}
          onAddFact={() => navigate('/career')}
        />
      )}
      {w.step === 4 && template && (
        <ReviewStep w={w} template={template} set={set} />
      )}
      <Box display="flex" justifyContent="flex-end" alignItems="center" mt="6" gap="3">
        {save.isError && <Text fontSize="sm" color="app.missText" role="alert">Could not save the document.</Text>}
        <Button variant="ghost" color="app.link" disabled={w.step === 1} onClick={() => go((w.step - 1) as Wizard['step'])}>
          Back
        </Button>
        <Button bg="app.primary" color="app.onPrimary" disabled={!canNext} loading={save.isPending} onClick={next}>
          {w.step === 4 ? 'Done' : 'Next'}
        </Button>
      </Box>
    </>
  )
}
