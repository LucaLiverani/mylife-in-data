declare module 'kafkajs-snappy' {
  import { CompressionCodec } from 'kafkajs';
  const SnappyCodec: CompressionCodec;
  export default SnappyCodec;
}
