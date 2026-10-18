import type { ReactNode } from 'react'
import { Info, WarningCircle, WarningOctagon } from '@phosphor-icons/react'
import './Notice.css'

type Tone = 'info' | 'warning' | 'error'

const ICONS = { info: Info, warning: WarningCircle, error: WarningOctagon }

interface NoticeProps {
  tone: Tone
  children: ReactNode
  action?: ReactNode
}

export function Notice({ tone, children, action }: NoticeProps) {
  const Icon = ICONS[tone]
  return (
    <div className={`notice notice--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon className="notice__icon" size={18} weight="fill" aria-hidden="true" />
      <div className="notice__body">{children}</div>
      {action}
    </div>
  )
}
