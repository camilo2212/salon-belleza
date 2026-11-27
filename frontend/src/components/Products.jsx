import { SALON } from '../config'
import { money } from '../format'

export default function Products({ products }) {
  // Si todavía no hay productos cargados en el panel, la sección no se muestra.
  if (!Array.isArray(products) || products.length === 0) return null

  return (
    <section id="productos" className="section">
      <div className="wrap">
        <h2>Productos</h2>
        <p className="lede">
          Los encuentras en el salón.
          {SALON.whatsapp && ' Escríbenos por WhatsApp si quieres separar uno.'}
        </p>

        <ul className="shelf">
          {products.map((p) => (
            <li className="product" key={p.id}>
              <div className="product-img">
                {p.image ? (
                  <img src={p.image} alt={p.name} loading="lazy" />
                ) : (
                  <span aria-hidden="true">{p.name.charAt(0)}</span>
                )}
              </div>
              <h3>{p.name}</h3>
              <p className="product-price">
                {money(p.price)}
                {!p.in_stock && <span className="tag-out">Agotado</span>}
              </p>
              {p.description && <p className="muted product-desc">{p.description}</p>}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
