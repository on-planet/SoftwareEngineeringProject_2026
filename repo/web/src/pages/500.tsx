export default function ServerErrorPage() {
  return (
    <div className="page">
      <section className="card">
        <h1 className="page-title">500</h1>
        <p className="helper" style={{ marginTop: 12 }}>
          服务器暂时不可用，请稍后再试。
        </p>
      </section>
    </div>
  );
}
