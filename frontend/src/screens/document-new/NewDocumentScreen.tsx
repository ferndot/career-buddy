import { Box, Button, Text } from '@chakra-ui/react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingState, toaster } from '../../components'
import { DocsStep } from './DocsStep'
import { DocTabs } from './DocTabs'
import { DownloadStep } from './DownloadStep'
import { FactsPicker } from './FactsPicker'
import { JobStep } from './JobStep'
import { MissingPane } from './MissingPane'
import { StepIndicator } from './StepIndicator'
import { TemplateStep } from './TemplateStep'
import { clearDraft, loadDraft, missingInputs, saveDraft, type DocDraft, type DocKind, type Wizard } from './state'
import { useSaved } from './useSaved'
import { useWizardData } from './useWizardData'

const LAST = 5

export function NewDocumentScreen() {
  const navigate = useNavigate()
  const [w, setW] = useState<Wizard>(loadDraft)
  const set = (patch: Partial<Wizard>) => setW((prev) => ({ ...prev, ...patch }))
  const setDoc = (kind: DocKind) => (patch: Partial<DocDraft>) =>
    setW((prev) => ({ ...prev, docs: { ...prev.docs, [kind]: { ...prev.docs[kind], ...patch } } }))
  useEffect(() => saveDraft(w), [w]) // the draft saves itself

  const { templates, profile, review, loading, hasJob } = useWizardData(w, setW)
  const { save, saved } = useSaved(w, templates.data)
  const [finishing, setFinishing] = useState(false)
  const [finishError, setFinishError] = useState(false)

  const ready = (k: DocKind) => !missingInputs(w.docs[k], templates.data?.find((t) => t.id === w.docs[k].templateId))
  const canNext =
    w.step === 1 ? hasJob || w.noJob : w.step === 2 ? w.kinds.length > 0 : w.step === 3 ? w.prefilled && w.kinds.every((k) => w.docs[k].seeded) : w.step === 4 ? w.kinds.every(ready) : true
  const go = (step: Wizard['step']) => set({ step })
  const finish = async () => {
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
  const next = () => (w.step < LAST ? go((w.step + 1) as Wizard['step']) : void finish())

  const active = w.active
  const loaded = templates.data && (w.step < 3 || profile.data)
  const failed = templates.isError || profile.isError
  const body = !loaded ? (
    failed ? <Text color="app.muted">Could not load your profile and templates.</Text> : <LoadingState text="Loading your profile and templates..." />
  ) :w.step === 3 ? (
    <>
      <MissingPane w={w} review={review} set={set} />
      {profile.data && <FactsPicker doc={w.docs[active]} setDoc={setDoc(active)} profile={profile.data} hasJob={hasJob} loading={loading} />}
    </>
  ) : w.step === 4 ? (
    <TemplateStep w={w} kind={active} templates={templates.data!} setDoc={setDoc(active)} />
  ) : (
    <DownloadStep key={active} kind={active} saved={saved.includes(active)} save={() => save(active)} />
  )

  return (
    <>
      <StepIndicator current={w.step} />
      {w.step === 1 && <JobStep w={w} set={set} />}
      {w.step === 2 && <DocsStep w={w} set={set} />}
      {w.step >= 3 && (
        <Box display="flex" flexDirection={{ base: 'column', md: 'row' }} gap="5" alignItems={{ md: 'flex-start' }}>
          <DocTabs w={w} templates={templates.data ?? []} saved={saved} onSelect={(k) => set({ active: k })} />
          <Box flex="1" minW="0" w="full">{body}</Box>
        </Box>
      )}
      <Box display="flex" justifyContent="flex-end" alignItems="center" mt="6" gap="3">
        {finishError && <Text fontSize="sm" color="app.missText" role="alert">Could not save the documents.</Text>}
        <Button variant="ghost" color="app.link" disabled={w.step === 1} onClick={() => go((w.step - 1) as Wizard['step'])}>
          Back
        </Button>
        <Button bg="app.primary" color="app.onPrimary" disabled={!canNext} loading={finishing} onClick={next}>
          {w.step === LAST ? 'Done' : 'Next'}
        </Button>
      </Box>
    </>
  )
}
