import type { NextPageContext } from "next";

type ErrorPageProps = {
  statusCode?: number;
};

function getMessage(statusCode?: number) {
  if (statusCode === 404) {
    return "页面不存在";
  }
  if (statusCode === 500) {
    return "服务器内部错误";
  }
  return "页面加载失败";
}

export default function ErrorPage({ statusCode }: ErrorPageProps) {
  return (
    <div className="page">
      <section className="card">
        <h1 className="page-title">{statusCode ? `${statusCode}` : "错误"}</h1>
        <p className="helper" style={{ marginTop: 12 }}>
          {getMessage(statusCode)}
        </p>
      </section>
    </div>
  );
}

ErrorPage.getInitialProps = ({ res, err }: NextPageContext): ErrorPageProps => {
  const statusCode = res?.statusCode ?? err?.statusCode ?? 500;
  return { statusCode };
};
