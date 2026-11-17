import { Box, Button, Flex, Text } from '@chakra-ui/react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingState, toaster, useActivityLog } from '../../components'
import { DocsStep } from './DocsStep'
import { DocTabs } from './DocTabs'
import { DownloadStep } from './DownloadStep'
import { JobStep } from './JobStep'
import { MissingPane } from './MissingPane'
import { ReviewStep } from './ReviewStep'
import { StepIndicator } from './StepIndicator'
import { TemplateStep } from './TemplateStep'
import { clearDraft, loadDraft, missingInputs, saveDraft, type DocDraft, type DocKind, type Wizard } from './state'
import { useReview } from './useReview'
import { useSaved } from './useSaved'
import { useWizardData } from './useWizardData'

const LAST = 5

export function NewDocumentScreen() {
  const navigate = useNavigate()
  const [w, setW] = useState<Wizard>(loadDraft)
  // A review belongs to the posting it read: new posting text drops it.
  const set = (patch: Partial<Wizard>) =>
    setW((prev) => ({ ...prev, ...patch, ...(patch.jobText !== undefined && patch.jobText !== prev.jobText ? { review: null } : {}) }))
  const setDoc = (kind: DocKind) => (patch: Partial<DocDraft>) =>
    setW((prev) => ({ ...prev, docs: { ...prev.docs, [kind]: { ...prev.docs[kind], ...patch } } }))
  useEffect(() => saveDraft(w), [w]) // the draft saves itself

  const { templates, review, hasJob } = useWizardData(w, setW)
  const newLog = useActivityLog()
  const reviewing = useReview(w, set, newLog)
  const { save, saved } = useSaved(w, templates.data, newLog)
  const [finishing, setFinishing] = useState(false)
  const [finishError, setFinishError] = useState(false)

  const ready = (k: DocKind) => !missingInputs(w.docs[k], templates.data?.find((t) => t.id === w.docs[k].templateId))
  // A document whose text the model failed to write does not go on: it waits for a generate that works.
  const generationFailed = w.kinds.some((k) => w.docs[k].genError)
  const canNext =
    w.step === 1 ? hasJob || w.noJob : w.step === 2 ? w.kinds.length > 0 : w.step === 4 ? w.kinds.every(ready) && !generationFailed : true
  const go = (step: Wizard['step']) => set({ step })
  const finish = async () => {
    if (generationFailed) return
    setFinishing(true)
    setFinishError(false)
    try {
      const docs = await Promise.all(w.kinds.map(save))
      clearDraft()
      toaster.create({ type: 'success', title: docs.length > 1 ? 'Documents saved' : 'Document saved', description: docs.map((d) => d.label).join(', ') })
      navigate('/documents')
    } catch {
      setFinishError(true)
      setFinishing(false)
    }
  }
  const next = () => (w.step === 1 ? reviewing.start() : w.step < LAST ? go((w.step + 1) as Wizard['step']) : void finish())

  const active = w.active
  const body = !templates.data ? (
    templates.isError ? <Text color="app.muted">Could not load the templates.</Text> : <LoadingState text="Loading the templates..." />
  ) : w.step === 4 ? (
    <TemplateStep w={w} kind={active} templates={templates.data} setDoc={setDoc(active)} newLog={newLog} />
  ) : (
    <DownloadStep key={active} kind={active} saved={saved.includes(active)} save={() => save(active)} newLog={newLog} blocked={w.docs[active].genError} />
  )

  return (
    <>
      <Flex justifyContent="space-between" alignItems="center" gap="3" mb="6" wrap="wrap">
        <StepIndicator current={w.step} />
        <Flex alignItems="center" gap="3">
          {finishError && <Text fontSize="sm" color="app.missText" role="alert">Could not save the documents.</Text>}
          <Button variant="ghost" color="app.link" disabled={w.step === 1} onClick={() => go((w.step - 1) as Wizard['step'])}>
            Back
          </Button>
          <Button bg="app.primary" color="app.onPrimary" disabled={!canNext || reviewing.active} loading={finishing} onClick={next}>
            {w.step === LAST ? 'Done' : 'Next'}
          </Button>
        </Flex>
      </Flex>
      {w.step === 1 && (reviewing.active ? <ReviewStep failed={reviewing.failed} reason={reviewing.reason} retry={reviewing.start} skip={reviewing.skip} /> : <JobStep w={w} set={set} />)}
      {w.step === 2 && <DocsStep w={w} set={set} />}
      {w.step === 3 && <MissingPane w={w} review={review} set={set} hasJob={hasJob} />}
      {w.step >= 4 && (
        <Box display="flex" flexDirection={{ base: 'column', md: 'row' }} gap="5" alignItems={{ md: 'flex-start' }}>
          <DocTabs w={w} templates={templates.data ?? []} saved={saved} onSelect={(k) => set({ active: k })} />
          <Box flex="1" minW="0" w="full">{body}</Box>
        </Box>
      )}
    </>
  )
}
