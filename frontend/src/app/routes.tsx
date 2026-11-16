import { Navigate, Route, Routes } from 'react-router-dom'
import { CareerScreen } from '../screens/career'
import { DocumentsScreen } from '../screens/documents'
import { NewDocumentScreen } from '../screens/document-new'
import { SettingsScreen } from '../screens/settings'
import { SourcesScreen } from '../screens/sources'
import { AppShell } from './AppShell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/sources" replace />} />
        <Route path="/sources" element={<SourcesScreen />} />
        <Route path="/career" element={<CareerScreen />} />
        <Route path="/documents" element={<DocumentsScreen />} />
        <Route path="/documents/new" element={<NewDocumentScreen />} />
        <Route path="/settings" element={<SettingsScreen />} />
        <Route path="*" element={<Navigate to="/sources" replace />} />
      </Route>
    </Routes>
  )
}
