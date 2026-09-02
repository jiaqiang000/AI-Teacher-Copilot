import { generateStaticParamsFor, importPage } from "nextra/pages";

import { useMDXComponents as getMDXComponents } from "../../../../mdx-components";

// Nextra 3 在 Next 16 下部分文档页预渲染报 children 校验错误(上游兼容):
// 跳过构建期静态导出,运行时仍正常渲染。
export const dynamic = "force-dynamic";

export const generateStaticParams = generateStaticParamsFor("mdxPath");

export async function generateMetadata(props) {
  const params = await props.params;
  const { metadata } = await importPage(params.mdxPath, params.lang);
  return metadata;
}

// eslint-disable-next-line @typescript-eslint/unbound-method
const Wrapper = getMDXComponents().wrapper;

export default async function Page(props) {
  const params = await props.params;
  const {
    default: MDXContent,
    toc,
    metadata,
    sourceCode,
  } = await importPage(params.mdxPath, params.lang);
  return (
    <Wrapper toc={toc} metadata={metadata} sourceCode={sourceCode}>
      <MDXContent {...props} params={params} />
    </Wrapper>
  );
}
