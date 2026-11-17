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
import { DocPreview } from './DocPreview'
import { WritingStep } from './WritingStep'
import { useWriting } from './useWriting'
import { StepIndicator } from './StepIndicator'
import { TemplateStep } from './TemplateStep'
import { MAX_INSTRUCTIONS } from '../documents/api'
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
  const [writing, setWriting] = useState(false) // the interstitial between the template step and the last step
  const [finishing, setFinishing] = useState(false)
  const [finishError, setFinishError] = useState(false)

  const ready = (k: DocKind) => !missingInputs(w.docs[k], templates.data?.find((t) => t.id === w.docs[k].templateId))
  // A document whose text the model failed to write does not go on: it waits for a generate that works.
  const generationFailed = w.kinds.some((k) => w.docs[k].genError)
  const canNext =
    w.step === 1 ? hasJob || w.noJob : w.step === 2 ? w.kinds.length > 0 : w.step === 4 ? w.kinds.every((k) => ready(k) && w.docs[k].instructions.length <= MAX_INSTRUCTIONS) : w.step === 5 ? !generationFailed : true
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
  const writer = useWriting(w, setDoc, newLog, () => {
    setWriting(false)
    go(LAST)
  })
  const next = () => {
    if (w.step === 1) return reviewing.start()
    if (w.step === 4) {
      setWriting(true)
      return writer.start()
    }
    if (w.step < LAST) return go((w.step + 1) as Wizard['step'])
    void finish()
  }

  const active = w.active
  const body = w.step < 4 ? null : !templates.data ? (
    templates.isError ? <Text color="app.muted">Could not load the templates.</Text> : <LoadingState text="Loading the templates..." />
  ) : writing ? (
    <WritingStep failed={writer.failed} reason={writer.reason} retry={writer.start} back={() => setWriting(false)} />
  ) : w.step === 4 ? (
    <TemplateStep w={w} kind={active} templates={templates.data} setDoc={setDoc(active)} />
  ) : (
    <Flex direction={{ base: 'column', md: 'row' }} gap="5" alignItems="flex-start" wrap="wrap">
      <Box flex="1.4 1 320px" minW="0">
        <DocPreview w={w} kind={active} ready={ready(active)} setDoc={setDoc(active)} editable />
      </Box>
      <Box flex="1 1 280px" minW="0">
        <DownloadStep key={active} kind={active} saved={saved.includes(active)} save={() => save(active)} newLog={newLog} blocked={w.docs[active].genError} />
      </Box>
    </Flex>
  )

  return (
    <>
      <Flex justifyContent="space-between" alignItems="center" gap="3" mb="6" wrap="wrap">
        <StepIndicator current={w.step} />
        <Flex alignItems="center" gap="3">
          {finishError && <Text fontSize="sm" color="app.missText" role="alert">Could not save the documents.</Text>}
          <Button variant="ghost" color="app.link" disabled={w.step === 1 || writing} onClick={() => go((w.step - 1) as Wizard['step'])}>
            Back
          </Button>
          <Button bg="app.primary" color="app.onPrimary" disabled={!canNext || reviewing.active || writing} loading={finishing} onClick={next}>
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
