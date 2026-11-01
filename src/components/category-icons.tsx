import { FileText, Lightbulb, BookOpen, Ellipsis, Bookmark, Leaf, Coffee, Compass } from 'lucide-react'

export const categoryIcons = [
  { id: 'file-text', label: '文档', Icon: FileText },
  { id: 'lightbulb', label: '灯泡', Icon: Lightbulb },
  { id: 'book-open', label: '书本', Icon: BookOpen },
  { id: 'ellipsis', label: '更多', Icon: Ellipsis },
  { id: 'bookmark', label: '书签', Icon: Bookmark },
  { id: 'leaf', label: '叶子', Icon: Leaf },
  { id: 'coffee', label: '咖啡', Icon: Coffee },
  { id: 'compass', label: '指南针', Icon: Compass },
] as const
const defaults: Record<string, string> = { 随笔: 'file-text', 灵感: 'lightbulb', 书摘: 'book-open', 其他: 'ellipsis' }
export function categoryIconId(category: string, icons?: Record<string, string>) { return icons?.[category] || defaults[category] || 'file-text' }
export function categoryIcon(id: string) { return categoryIcons.find(x => x.id === id)?.Icon || FileText }

export function IconPicker({ value, onChange, disabled }: { value: string; onChange: (value: string) => void; disabled: boolean }) {
  return <fieldset className="category-icon-picker" disabled={disabled}><legend>分类图标</legend><div className="category-icon-options">
    {categoryIcons.map(({ id, label, Icon }) => <label key={id} title={label}><input type="radio" name="category-icon" value={id} checked={value === id} onChange={() => onChange(id)} /><span><Icon aria-hidden="true" /><span>{label}</span></span></label>)}
  </div></fieldset>
}
