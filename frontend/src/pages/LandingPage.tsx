import { useState } from 'react'
import { Header } from '../components/Header'
import { Brand } from '../components/Brand'
import { Botanical } from '../components/Botanical'
import { LeafSprig } from '../components/LeafSprig'
import { RoleSwitch } from '../components/RoleSwitch'
import { SignupPreview } from '../components/SignupPreview'
import { ProductCard } from '../components/ProductCard'
import { getFeaturedProducts } from '../services/products'
import type { AccountRole } from '../types/account'

const currentYear = new Date().getFullYear()

const buyerSteps = [
  [
    'Find your kind of good.',
    'A vision for discovering the backyard growers, small bakeries, and independent shops that make a neighborhood feel like home.',
  ],
  [
    'Get to know the price.',
    'Our planned Fair Price Passport will share seller-approved cost details, distinguish estimates from evidence, and explain what’s still unknown.',
  ],
  [
    'Choose with understanding.',
    'See the work behind what you buy, ask better questions, and decide what matters to you. Shopping and checkout are still to come.',
  ],
]
const sellerSteps = [
  [
    'Start with what you make.',
    'A dozen eggs, your first sourdough loaves, a small batch of soap. The future seller workspace starts with your goods and your inputs.',
  ],
  [
    'Make room for your work.',
    'Planned pricing tools will account for materials, time, and overhead, with estimates clearly labeled and your quality requirements protected.',
  ],
  [
    'Tell the story behind it.',
    'You’ll choose which cost details to share with buyers. Publishing, pricing analysis, and payments are still being built.',
  ],
]

export function LandingPage() {
  const [role, setRole] = useState<AccountRole>('buyer')
  const [accountRole, setAccountRole] = useState<AccountRole>('buyer')
  const [heroFailed, setHeroFailed] = useState(false)
  const buyer = role === 'buyer'

  function switchRole(next: AccountRole) {
    setRole(next)
    setAccountRole(next)
    setHeroFailed(false)
  }

  return (
    <div id="home">
      <Header role={role} />
      <main id="main">
        <section className="hero page-width" aria-labelledby="welcome-heading">
          <div className="hero-copy">
            <RoleSwitch role={role} onChange={switchRole} />
            <div className="hero-text" key={role}>
              <p className="eyebrow">
                <LeafSprig />{' '}
                {buyer
                  ? 'Your neighborhood, a little closer'
                  : 'For the hands that make it happen'}
              </p>
              <h1 id="welcome-heading">
                {buyer ? (
                  <>
                    Good things grow
                    <br />
                    <em>close to home.</em>
                  </>
                ) : (
                  <>
                    Small batches.
                    <br />
                    <em>Worth every bit.</em>
                  </>
                )}
              </h1>
              <p className="hero-description">
                {buyer
                  ? 'Backyard eggs. A beautiful loaf. Something made with care, just down the road. Meet FairMade: a farmers market for your everyday, with a little more understanding behind every price.'
                  : 'For the early risers, the backyard growers, and the “just one more loaf” bakers. We’re building a way to understand your costs, value your time, and share what makes your goods worth it.'}
              </p>
              <div className="hero-actions">
                <a
                  className="button-primary"
                  href={buyer ? '#marketplace' : '#create-account'}
                >
                  {buyer
                    ? 'Take a look around'
                    : 'Find your place at the market'}{' '}
                  <span aria-hidden="true">↗</span>
                </a>
                <a className="text-link" href="#how-it-works">
                  How it works <span aria-hidden="true">→</span>
                </a>
              </div>
              <p className="hero-footnote">
                {buyer
                  ? 'Good neighbors. Thoughtful goods. Prices with a story.'
                  : 'Your materials. Your time. Your quality, protected.'}
              </p>
            </div>
          </div>
          <div
            className={`hero-still-life ${buyer ? '' : 'seller-still-life'}`}
          >
            <div className="hero-photo">
              {heroFailed ? (
                <div className="image-fallback">
                  {buyer
                    ? 'From the neighborhood oven'
                    : 'From the backyard coop'}
                </div>
              ) : (
                <img
                  src={
                    buyer
                      ? '/images/market-bread.jpg'
                      : '/images/backyard-eggs.jpg'
                  }
                  alt={
                    buyer
                      ? 'Flour-dusted and seeded bread loaves on a rustic table'
                      : 'A carton of richly colored backyard eggs'
                  }
                  width="1400"
                  height="1000"
                  fetchPriority="high"
                  onError={() => setHeroFailed(true)}
                />
              )}
            </div>
            <div className="market-stamp">
              <span>Grown. Made.</span>
              <LeafSprig />
              <span>Close to home.</span>
            </div>
            <figure className="little-postcard">
              <img
                src={
                  buyer
                    ? '/images/backyard-eggs.jpg'
                    : '/images/market-bread.jpg'
                }
                alt={
                  buyer
                    ? 'Brown and pale blue eggs in a carton'
                    : 'Freshly baked rustic loaves'
                }
                width="260"
                height="300"
              />
              <figcaption>
                {buyer
                  ? 'A little backyard goodness'
                  : 'Made with flour & patience'}
              </figcaption>
            </figure>
            <div className="hero-handwriting">
              {buyer
                ? 'From our neighbors, with care.'
                : 'There’s room for your kind of good.'}
            </div>
            <Botanical className="hero-botanical" />
          </div>
        </section>

        <div className="market-ribbon">
          <span
            className="ribbon-flourish ribbon-flourish-top"
            aria-hidden="true"
          >
            <Botanical />
            <Botanical />
          </span>
          <div className="page-width">
            <span>
              <LeafSprig /> Rooted in community
            </span>
            <span>
              <LeafSprig /> Quality worth protecting
            </span>
            <span>
              <LeafSprig /> A little more price clarity
            </span>
          </div>
          <span
            className="ribbon-flourish ribbon-flourish-bottom"
            aria-hidden="true"
          >
            <Botanical />
            <Botanical />
          </span>
        </div>

        <section
          id="marketplace"
          className="market-section page-width"
          aria-labelledby="market-heading"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">
                {buyer
                  ? 'A glimpse of the market'
                  : 'Big care comes in small batches'}
              </p>
              <h2 id="market-heading">
                {buyer ? (
                  <>
                    From the coop, the kitchen,
                    <br />
                    <em>and the hands next door.</em>
                  </>
                ) : (
                  <>
                    For your first dozen.
                    <br />
                    <em>And your next chapter.</em>
                  </>
                )}
              </h2>
            </div>
            <div className="section-aside">
              <p>
                {buyer
                  ? 'The kinds of good things we’re making room for. Familiar favorites, with people behind them.'
                  : 'You don’t need a storefront to have something worth sharing. We’re building with small producers in mind.'}
              </p>
              <span className="small-tag">
                Illustrative market · not live listings
              </span>
            </div>
          </div>
          {buyer ? (
            <>
              <div className="product-grid">
                {getFeaturedProducts().map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
              <p className="sample-disclaimer">
                A little inspiration, not a live market. Products, sellers, and
                USD prices are illustrative; photos don’t verify product claims
                or local availability.
              </p>
            </>
          ) : (
            <div className="maker-grid">
              <article className="maker-feature">
                <img
                  src="/images/backyard-eggs.jpg"
                  alt="A dozen mixed-color eggs in a carton"
                  loading="lazy"
                  width="600"
                  height="700"
                />
                <div>
                  <p className="eyebrow">Backyard growers & small farms</p>
                  <h3>Good work starts small.</h3>
                  <p>
                    Your feed, your time, the care you put in. The little costs
                    deserve a place in the bigger picture.
                  </p>
                </div>
              </article>
              <article className="maker-feature">
                <img
                  src="/images/market-bread.jpg"
                  alt="Rustic bread loaves with wheat stalks"
                  loading="lazy"
                  width="600"
                  height="700"
                />
                <div>
                  <p className="eyebrow">Home bakers & neighborhood shops</p>
                  <h3>More than flour and water.</h3>
                  <p>
                    The early mornings and patient practice count, too. Your
                    craft deserves room to keep growing.
                  </p>
                </div>
              </article>
            </div>
          )}
        </section>

        <section
          id="how-it-works"
          className="how-section"
          aria-labelledby="how-heading"
        >
          <div className="page-width">
            <div className="how-heading">
              <div>
                <p className="eyebrow">A thoughtful way forward</p>
                <h2 id="how-heading">
                  {buyer ? (
                    <>
                      Know a little more.
                      <br />
                      <em>Feel a little closer.</em>
                    </>
                  ) : (
                    <>
                      Made with care.
                      <br />
                      <em>Priced with understanding.</em>
                    </>
                  )}
                </h2>
              </div>
              <p className="coming-note">
                What we’re growing toward
                <br />
                <span>
                  Pricing tools, live listings, and checkout are coming in
                  future releases.
                </span>
              </p>
            </div>
            <div className="steps-grid">
              {(buyer ? buyerSteps : sellerSteps).map(
                ([title, text], index) => (
                  <article key={title}>
                    <span className="step-number">
                      0{index + 1}
                      <span aria-hidden="true"> /</span>
                    </span>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </article>
                ),
              )}
            </div>
            <a className="text-link" href="#create-account">
              {buyer ? 'Make yourself at home' : 'Explore the seller signup'}{' '}
              <span aria-hidden="true">↗</span>
            </a>
          </div>
        </section>

        <section
          id="our-promise"
          className="promise-section page-width"
          aria-labelledby="promise-heading"
        >
          <Botanical className="promise-botanical" />
          <div>
            <p className="eyebrow">A promise we’re growing by</p>
            <h2 id="promise-heading">
              “A good market leaves room
              <br />
              for the hands that make
              <br />
              <em>and the homes that welcome.”</em>
            </h2>
            <p>
              We believe a price deserves an explanation. The materials, the
              time, the care—and an honest word about what we know and what we
              don’t. That’s the kind of market we’re here to build.
            </p>
            <span className="promise-signature">With care, FairMade</span>
          </div>
          <Botanical className="promise-botanical mirrored" />
        </section>

        <SignupPreview
          key={role}
          role={accountRole}
          onRoleChange={setAccountRole}
        />
      </main>
      <footer className="page-width site-footer">
        <div>
          <Brand />
          <p>A little more local. A little more understood.</p>
        </div>
        <div className="footer-links">
          <a href="#marketplace">{buyer ? 'The market' : 'For our makers'}</a>
          <a href="#our-promise">Our promise</a>
          <a href="#create-account">Find your place ↗</a>
        </div>
        <div className="footer-bottom">
          <p>© {currentYear} FairMade · A farmers market in the making.</p>
          <p>Frontend preview · Built for the PayPal AI Hackathon</p>
        </div>
      </footer>
    </div>
  )
}
