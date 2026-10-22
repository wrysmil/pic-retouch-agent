import BrandMark from '@/components/BrandMark'

const ICP_NUMBER = '湘ICP备2026045370号-1'

export default function LandingFooter() {
  return (
    <footer className="border-line border-t">
      <div className="text-faint mx-auto flex max-w-5xl flex-col gap-2 px-6 py-8 text-xs">
        <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
          <BrandMark size="sm">
            <span className="text-muted font-medium">映造</span>
          </BrandMark>
          <p>为电商运营与内容创作者打造的商品物料工作台</p>
        </div>
        <p className="text-center sm:text-right">
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-brand-strong transition-colors"
          >
            {ICP_NUMBER}
          </a>
        </p>
      </div>
    </footer>
  )
}