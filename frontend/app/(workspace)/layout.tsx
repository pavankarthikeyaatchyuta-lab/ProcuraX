import {Suspense} from 'react';
import {Shell} from '../../components/shell';
export default function WorkspaceLayout({children}:{children:React.ReactNode}){return <Suspense fallback={<p>Loading workspace…</p>}><Shell>{children}</Shell></Suspense>}
